"""
Tracker for SNMPv3 authentication failures.
"""

import uuid
import logging
from datetime import datetime, UTC
from typing import List, Dict, Any

from mutt.storage.database import Database

logger = logging.getLogger(__name__)


class AuthFailureTracker:
    """Tracks and manages SNMPv3 authentication failure records in the database."""

    def __init__(self, database: Database):
        """
        Initialize the tracker.
        
        Args:
            database: Database instance for storage operations
        """
        self.database = database

    async def record_failure(self, username: str, hostname: str) -> None:
        """
        Record a failed authentication attempt.
        
        If a record for the username exists, increments failure count and updates time.
        Otherwise, creates a new record.
        
        Args:
            username: The SNMPv3 username that failed authentication
            hostname: The hostname or IP address the failure originated from
        """
        try:
            current_time = datetime.now(UTC).isoformat()
            
            # Using INSERT OR REPLACE style logic with ON CONFLICT
            query = """
            INSERT INTO snmpv3_auth_failures (id, username, hostname, num_failures, last_failure)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(username) DO UPDATE SET
                num_failures = num_failures + 1,
                last_failure = excluded.last_failure,
                hostname = excluded.hostname
            """
            
            await self.database.execute(
                query,
                (str(uuid.uuid4()), username, hostname, current_time)
            )
            await self.database.connection.commit()
            logger.info(f"[AuthFailureTracker] Recorded failure for {username} from {hostname}")
            
        except Exception as e:
            logger.error(f"Error recording auth failure for {username}: {e}")

    async def clear_failure(self, username: str) -> None:
        """
        Clear all failure records for a specific username.
        
        Args:
            username: The username to clear failures for
        """
        try:
            query = "DELETE FROM snmpv3_auth_failures WHERE username = ?"
            await self.database.execute(query, (username,))
            await self.database.connection.commit()
            logger.info(f"[AuthFailureTracker] Cleared failures for {username}")
            
        except Exception as e:
            logger.error(f"Error clearing auth failures for {username}: {e}")

    async def get_all_failures(self) -> List[Dict[str, Any]]:
        """
        Retrieve all authentication failure records.
        
        Returns:
            List of dictionaries containing failure details, sorted by failure count descending.
        """
        try:
            query = """
            SELECT username, hostname, num_failures, last_failure
            FROM snmpv3_auth_failures
            ORDER BY num_failures DESC, last_failure DESC
            """

            cursor = await self.database.execute(query)
            rows = await cursor.fetchall()

            return [
                {
                    "username": row[0],
                    "hostname": row[1],
                    "num_failures": row[2],
                    "last_failure": row[3]
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Error retrieving auth failures: {e}")
            return []
