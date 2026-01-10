"""
Database module for Mutt - Async SQLite storage for messages.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

import aiosqlite

from mutt.models.message import Message, SyslogMessage, SNMPTrap, MessageType, Severity
from .schema import SCHEMA_SQL

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database for storing and retrieving messages."""
    
    def __init__(self, db_path: str):
        """
        Initialize the database.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None
        
    async def __aenter__(self) -> "Database":
        """Enter async context manager."""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        if self.connection:
            await self.connection.close()
            
    async def initialize(self):
        """
        Initialize the database connection and create tables.
        """
        self.connection = await aiosqlite.connect(self.db_path)
        # Create tables
        await self.connection.executescript(SCHEMA_SQL)
        await self.connection.commit()
            
    async def store_message(self, msg: Message):
        """
        Store a message in the database.
        """
        if not self.connection:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        # Prepare metadata based on message type
        metadata = dict(msg.metadata)
        
        if isinstance(msg, SyslogMessage):
            metadata.update({
                "facility": msg.facility,
                "priority": msg.priority,
                "hostname": msg.hostname,
                "process_name": msg.process_name,
                "process_id": msg.process_id
            })
        elif isinstance(msg, SNMPTrap):
            metadata.update({
                "oid": msg.oid,
                "varbinds": msg.varbinds,
                "version": msg.version
            })
        
        # Insert message into database
        await self.connection.execute("""
            INSERT INTO messages (
                id, timestamp, source_ip, type, severity, payload, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            msg.id,
            msg.timestamp.isoformat(),
            msg.source_ip,
            msg.message_type.value,
            msg.severity.value,
            msg.payload,
            json.dumps(metadata)
        ))
        await self.connection.commit()
            
    async def execute(self, query: str, parameters: tuple = ()):
        """
        Execute a query on the database.
        """
        if not self.connection:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return await self.connection.execute(query, parameters)

    async def get_messages(self, limit: int = 100) -> List[Message]:
        """
        Retrieve messages from the database.
        """
        if not self.connection:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        async with self.connection.execute("""
            SELECT id, timestamp, source_ip, type, severity, payload, metadata
            FROM messages
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            messages: List[Message] = []
            
            for row in rows:
                msg_id, ts_str, source_ip, msg_type_str, sev_str, payload, meta_json = row
                
                messages.append(Message(
                    id=msg_id,
                    timestamp=datetime.fromisoformat(ts_str),
                    source_ip=source_ip,
                    message_type=MessageType(msg_type_str),
                    severity=Severity(sev_str),
                    payload=payload,
                    metadata=json.loads(meta_json)
                ))
                    
            return messages
