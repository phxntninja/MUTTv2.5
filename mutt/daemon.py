#!/usr/bin/env python3
"""
MUTT Daemon - Main daemon process for the MUTT system.
"""

import asyncio
import argparse
import signal
import sys
import os
from typing import Dict, Any, Optional

from mutt.config import load_config
from mutt.logger import setup_logging, get_logger
from mutt.listeners.syslog_listener import SyslogListener
from mutt.listeners.snmp_listener import SNMPListener
from mutt.processors.message_processor import MessageProcessor


class MUTTDaemon:
    """Main MUTT daemon class."""
    
    def __init__(self):
        """Initialize the MUTT daemon."""
        self.config: Optional[Dict[str, Any]] = None
        self.logger = get_logger(__name__)
        self.message_queue: Optional[asyncio.Queue] = None
        self.listeners = []
        self.processor: Optional[MessageProcessor] = None
        self.shutdown_event = asyncio.Event()
        
    async def main(self) -> None:
        """Main entry point for the MUTT daemon."""
        try:
            # Parse command line arguments
            args = self._parse_args()
            
            # Load configuration
            self.config = load_config(args.config)
            
            # Setup logging
            log_file = self.config.get('logging', {}).get('file', 'logs/mutt.log')
            debug = self.config.get('logging', {}).get('debug', False)
            setup_logging(log_file, debug=debug)
            
            # Re-initialize logger after setup
            self.logger = get_logger(__name__)
            self.logger.info("Starting MUTT daemon")
            
            # Create message queue
            self.message_queue = asyncio.Queue()
            
            # Start message processor first so it's ready for messages
            await self._start_processor()
            
            # Start listeners
            await self._start_listeners()
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Keep running until shutdown signal
            self.logger.info("MUTT daemon is running")
            await self.shutdown_event.wait()
            
            # Perform graceful shutdown
            await self.shutdown()
            
        except Exception as e:
            self.logger.error(f"Fatal error in MUTT daemon: {e}", exc_info=True)
            await self.shutdown()
            sys.exit(1)
    
    def _parse_args(self) -> argparse.Namespace:
        """Parse command line arguments."""
        parser = argparse.ArgumentParser(
            description="MUTT Daemon - Multi-Use Telemetry Transport"
        )
        parser.add_argument(
            '-c', '--config',
            type=str,
            default='config/mutt.yaml',
            help='Path to configuration file (default: config/mutt.yaml)'
        )
        return parser.parse_args()
    
    async def _start_listeners(self) -> None:
        """Start all configured listeners."""
        listeners_config = self.config.get('listeners', {})
        
        # Start Syslog listener if enabled
        syslog_config = listeners_config.get('syslog', {})
        if syslog_config.get('enabled', True):
            try:
                port = syslog_config.get('port', 5514)
                host = syslog_config.get('host', '0.0.0.0')
                syslog_listener = SyslogListener(
                    queue=self.message_queue,
                    port=port,
                    host=host
                )
                await syslog_listener.start()
                self.listeners.append(syslog_listener)
                self.logger.info(f"Syslog listener started on {host}:{port}")
            except Exception as e:
                self.logger.error(f"Failed to start Syslog listener: {e}")
        
        # Start SNMP listener if enabled
        snmp_config = listeners_config.get('snmp', {})
        if snmp_config.get('enabled', True):
            try:
                port = snmp_config.get('port', 5162)
                host = snmp_config.get('host', '0.0.0.0')
                snmp_listener = SNMPListener(
                    queue=self.message_queue,
                    port=port,
                    host=host
                )
                await snmp_listener.start()
                self.listeners.append(snmp_listener)
                self.logger.info(f"SNMP listener started on {host}:{port}")
            except Exception as e:
                self.logger.error(f"Failed to start SNMP listener: {e}")
        
        if not self.listeners:
            self.logger.warning("No listeners enabled in configuration")
    
    async def _start_processor(self) -> None:
        """Start the message processor."""
        try:
            self.processor = MessageProcessor(
                config=self.config,
                queue=self.message_queue
            )
            await self.processor.start()
            self.logger.info("Message processor started")
        except Exception as e:
            self.logger.error(f"Failed to start message processor: {e}")
            raise
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: self.shutdown_event.set()
                )
            except NotImplementedError:
                # Signal handlers are not implemented on Windows
                pass
        
        self.logger.debug("Signal handlers installed for SIGINT and SIGTERM")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the MUTT daemon."""
        self.logger.info("Initiating graceful shutdown...")
        
        # Stop listeners
        for listener in self.listeners:
            try:
                await listener.stop()
                self.logger.debug(f"Stopped listener: {type(listener).__name__}")
            except Exception as e:
                self.logger.error(f"Error stopping listener {type(listener).__name__}: {e}")
        
        # Stop message processor
        if self.processor:
            try:
                await self.processor.stop()
                self.logger.debug("Stopped message processor")
            except Exception as e:
                self.logger.error(f"Error stopping message processor: {e}")
        
        # Clear listeners list
        self.listeners.clear()
        
        self.logger.info("MUTT daemon shutdown complete")


def main() -> None:
    """Entry point for the MUTT daemon."""
    daemon = MUTTDaemon()
    
    try:
        asyncio.run(daemon.main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
