"""
Message Processor module for Mutt system.
Handles message processing pipeline: validation, matching, enrichment, routing, and storage.
"""

import asyncio
import yaml
import os
from typing import Dict, Any, List, Optional
import logging

from mutt.storage.database import Database
from mutt.storage.device_registry import DeviceRegistry
from mutt.storage.auth_failure_tracker import AuthFailureTracker
from mutt.processors.validator import Validator
from mutt.processors.pattern_matcher import PatternMatcher
from mutt.processors.enricher import Enricher
from mutt.processors.message_router import MessageRouter
from mutt.storage.buffer import FileBuffer
from mutt.storage.archive_manager import ArchiveManager
from mutt.logger import get_logger
from mutt.models.rules import AlertRule, PatternType, ActionType

logger = get_logger(__name__)


class MessageProcessor:
    """Main processor for handling incoming messages through the processing pipeline."""
    
    def __init__(self, config: Dict[str, Any], queue: asyncio.Queue):
        """
        Initialize the MessageProcessor with configuration and message queue.
        
        Args:
            config: Configuration dictionary
            queue: Asyncio queue for incoming messages
        """
        self.config = config
        self.queue = queue
        self.tasks = []
        self.running = False
        
        # Initialize components
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize all processing components."""
        # Database
        db_path = self.config['storage']['db_path']
        self.database = Database(db_path)
        
        # Other components
        self.device_registry = DeviceRegistry(self.database)
        self.auth_failure_tracker = AuthFailureTracker(self.database)
        
        # FileBuffer
        buffer_dir = self.config['storage'].get('buffer_dir', 'buffer')
        self.file_buffer = FileBuffer(buffer_dir)
        
        # Other components
        self.validator = Validator()
        
        # Load rules if rules_file exists in config
        rules = self._load_rules()
        self.pattern_matcher = PatternMatcher(rules)
        
        self.enricher = Enricher(self.device_registry)
        self.message_router = MessageRouter()
        
        # ArchiveManager
        archive_dir = self.config['storage'].get('archive_dir', 'archives')
        self.archive_manager = ArchiveManager(self.database, archive_dir)
        
        logger.info("MessageProcessor components initialized")
        
    def _load_rules(self) -> List[AlertRule]:
        """
        Load rules from YAML file if specified in config.
        
        Returns:
            List of AlertRule objects
        """
        rules_file = self.config.get('rules_file')
        alert_rules = []
        
        if rules_file and os.path.exists(rules_file):
            try:
                with open(rules_file, 'r') as f:
                    data = yaml.safe_load(f)
                
                if data and 'rules' in data:
                    for r in data['rules']:
                        try:
                            rule = AlertRule(
                                id=r['id'],
                                name=r['name'],
                                pattern_type=PatternType(r['pattern_type']),
                                pattern=r['pattern'],
                                actions=[ActionType(a) for a in r['actions']],
                                enabled=r.get('enabled', True)
                            )
                            alert_rules.append(rule)
                        except (KeyError, ValueError) as e:
                            logger.error(f"Error parsing rule {r.get('id', 'unknown')}: {e}")
                
                logger.info(f"Loaded {len(alert_rules)} rules from {rules_file}")
            except Exception as e:
                logger.error(f"Error loading rules file {rules_file}: {e}")
        
        return alert_rules
    
    async def start(self):
        """
        Start the message processor with background tasks.
        """
        if self.running:
            logger.warning("MessageProcessor already running")
            return
            
        self.running = True
        
        # Initialize database connection
        await self.database.initialize()
        
        # Start background tasks
        self.tasks = [
            asyncio.create_task(self.process_loop(), name="process_loop"),
            asyncio.create_task(self.batch_write_loop(), name="batch_write_loop"),
            asyncio.create_task(self.archive_loop(), name="archive_loop")
        ]
        
        logger.info("MessageProcessor started with 3 background tasks")
        
    async def stop(self):
        """
        Stop the message processor and clean up resources.
        """
        if not self.running:
            return
            
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
            
        # Wait for tasks to complete cancellation
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
        # Perform one final flush
        await self._final_flush()
        
        # Close database connection
        if self.database.connection:
            await self.database.connection.close()
        
        logger.info("MessageProcessor stopped")
        
    async def _final_flush(self):
        """Perform final flush of file buffer to database."""
        try:
            logger.info("Performing final flush before shutdown")
            messages = await self.file_buffer.flush()
            if messages:
                for msg in messages:
                    await self.database.store_message(msg)
                logger.info(f"Flushed {len(messages)} messages to database")
        except Exception as e:
            logger.error(f"Error during final flush: {e}")
    
    async def process_loop(self):
        """Main message processing loop."""
        logger.info("Message processing loop started")
        
        last_log_time = 0
        
        while self.running:
            try:
                # Get message from queue with timeout to allow graceful shutdown
                try:
                    # Metric: Log queue size periodically if backed up
                    qsize = self.queue.qsize()
                    current_time = asyncio.get_running_loop().time()
                    if qsize > 100 and (current_time - last_log_time) > 5.0:
                        logger.warning(f"Message queue depth high: {qsize} messages pending")
                        last_log_time = current_time
                        
                    msg = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                    
                # Process the message
                await self._process_message(msg)
                
                # Mark task as done
                self.queue.task_done()
                
            except asyncio.CancelledError:
                logger.info("Message processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in process_loop: {e}")
                continue
                
        logger.info("Message processing loop stopped")
        
    async def _process_message(self, msg):
        """Process a single message through the pipeline."""
        try:
            # 1. Validate
            if not self.validator.validate(msg):
                logger.warning(f"Message validation failed: {msg.id}")
                return
                
            # 2. Match patterns
            matching_rules = self.pattern_matcher.match(msg)
            
            # 3. Enrich
            await self.enricher.enrich(msg)
            
            # 4. Route
            await self.message_router.route(msg, matching_rules)
            
            # 5. Buffer for batch writing
            # Note: file_buffer now implements memory buffering to reduce I/O
            await self.file_buffer.write(msg)
            
            logger.debug(f"Processed message: {msg.id}")
            
        except Exception as e:
            logger.error(f"Error processing message {getattr(msg, 'id', 'unknown')}: {e}")
            
    async def batch_write_loop(self):
        """Batch write loop for periodically flushing buffered messages to database."""
        # Reduced default interval to 2s to prevent large backlog on disk
        flush_interval = self.config.get('batch_write_interval', 2)
        logger.info(f"Batch write loop started with {flush_interval}s interval")
        
        while self.running:
            try:
                await asyncio.sleep(flush_interval)
                
                # Flush messages from buffer
                messages = await self.file_buffer.flush()
                
                if messages:
                    # Store each message in database
                    for msg in messages:
                        await self.database.store_message(msg)
                        
                    logger.info(f"Batch write: flushed {len(messages)} messages to database")
                    
            except asyncio.CancelledError:
                logger.info("Batch write loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in batch_write_loop: {e}")
                
        logger.info("Batch write loop stopped")
        
    async def archive_loop(self):
        """Archive cleanup loop for daily cleanup of old messages."""
        archive_interval = 24 * 60 * 60  # 24 hours in seconds
        retention_days = self.config.get('retention_days', 30)
        logger.info(f"Archive loop started with daily interval, retention: {retention_days} days")
        
        while self.running:
            try:
                await asyncio.sleep(archive_interval)
                
                # Archive old messages
                await self.archive_manager.archive_old_messages(retention_days)
                
            except asyncio.CancelledError:
                logger.info("Archive loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in archive_loop: {e}")
                
        logger.info("Archive loop stopped")