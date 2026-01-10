"""
Device registry for storing and updating device information.
"""

from datetime import datetime
from typing import Optional

from mutt.storage.database import Database


class DeviceRegistry:
    """Registry for managing device information in the database."""
    
    def __init__(self, db: Database):
        """Initialize the device registry.
        
        Args:
            db: Database connection instance
        """
        self.db = db
    
    async def update_device(
        self, 
        ip: str, 
        hostname: Optional[str] = None, 
        snmp_version: Optional[str] = None
    ) -> None:
        """Update device information in the database.
        
        If the device exists, update the provided fields and set last_seen to current UTC time.
        If it doesn't exist, insert a new record.
        
        Args:
            ip: Device IP address (primary key)
            hostname: Optional hostname of the device
            snmp_version: Optional SNMP version used for communication
        """
        current_time = datetime.utcnow().isoformat()
        
        # Build the update query with ON CONFLICT clause
        query = """
        INSERT INTO devices (ip, hostname, snmp_version, last_seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ip) DO UPDATE SET
            hostname = COALESCE(excluded.hostname, devices.hostname),
            snmp_version = COALESCE(excluded.snmp_version, devices.snmp_version),
            last_seen = excluded.last_seen
        """
        
        await self.db.execute(
            query,
            (ip, hostname, snmp_version, current_time)
        )
        await self.db.connection.commit()
