"""
Archive manager for moving old messages from database to file storage.
"""

import datetime
import json
import os
from typing import List, Dict, Any

from mutt.storage.database import Database


class ArchiveManager:
    """Manages archiving of old messages to JSONL files and tracking in database."""
    
    def __init__(self, db: Database, archive_dir: str):
        """
        Initialize the ArchiveManager.
        
        Args:
            db: Database instance for message storage
            archive_dir: Directory where archive files will be stored
        """
        self.db = db
        self.archive_dir = archive_dir
        
        # Ensure archive directory exists
        os.makedirs(self.archive_dir, exist_ok=True)
    
    async def archive_old_messages(self, days_retention: int) -> None:
        """
        Archive messages older than the specified retention period.
        
        Args:
            days_retention: Number of days to retain messages before archiving
        """
        # Calculate cutoff date
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days_retention)
        cutoff_str = cutoff_date.isoformat()
        
        # Select messages older than cutoff
        query = """
            SELECT id, timestamp, source_ip, type, severity, payload, metadata
            FROM messages 
            WHERE timestamp < ?
            ORDER BY timestamp ASC
        """
        async with await self.db.execute(query, (cutoff_str,)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            return
        
        # Generate archive filename with current timestamp
        timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"archive_{timestamp_str}.jsonl"
        filepath = os.path.join(self.archive_dir, filename)
        
        # Write messages to JSONL file
        with open(filepath, 'w', encoding='utf-8') as f:
            for row in rows:
                msg_dict = {
                    "id": row[0],
                    "timestamp": row[1],
                    "source_ip": row[2],
                    "type": row[3],
                    "severity": row[4],
                    "payload": row[5],
                    "metadata": json.loads(row[6])
                }
                f.write(json.dumps(msg_dict) + '\n')
        
        # Calculate statistics for archive record
        timestamps = [row[1] for row in rows]
        start_date = min(timestamps)
        end_date = max(timestamps)
        record_count = len(rows)
        
        # Delete archived messages from database
        delete_query = "DELETE FROM messages WHERE timestamp < ?"
        await self.db.execute(delete_query, (cutoff_str,))
        
        # Insert archive record into archives table
        archive_query = """
            INSERT INTO archives (filename, start_date, end_date, record_count)
            VALUES (?, ?, ?, ?)
        """
        await self.db.execute(
            archive_query,
            (filename, start_date, end_date, record_count)
        )
        
        # Commit the transaction
        await self.db.connection.commit()
