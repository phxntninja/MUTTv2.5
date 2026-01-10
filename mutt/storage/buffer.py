"""
File buffer for persisting messages to disk before batch processing.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List

from mutt.models.message import Message, MessageType, Severity


class FileBuffer:
    """Buffer that persists messages to a JSONL file for durability."""
    
    def __init__(self, buffer_dir: str):
        """
        Initialize the file buffer.
        
        Args:
            buffer_dir: Directory where buffer files will be stored
        """
        self.buffer_dir = buffer_dir
        self.buffer_file = os.path.join(buffer_dir, "buffer_active.jsonl")
        
        # Create buffer directory if it doesn't exist
        os.makedirs(buffer_dir, exist_ok=True)
    
    async def write(self, msg: Message) -> None:
        """
        Write a message to the buffer file.
        
        Args:
            msg: Message object to serialize and write
        """
        # Convert message to dict for JSON serialization
        msg_dict = {
            "id": msg.id,
            "timestamp": msg.timestamp.isoformat(),
            "source_ip": msg.source_ip,
            "message_type": msg.message_type.value,
            "severity": msg.severity.value,
            "payload": msg.payload,
            "metadata": msg.metadata
        }
        
        # Serialize to JSON
        json_line = json.dumps(msg_dict)
        
        # Write to file asynchronously
        await asyncio.to_thread(self._write_sync, json_line)
    
    def _write_sync(self, json_line: str) -> None:
        """Synchronous helper for file writing."""
        with open(self.buffer_file, "a", encoding="utf-8") as f:
            f.write(json_line + "\n")
    
    async def flush(self) -> List[Message]:
        """
        Read all messages from buffer and clear the file.
        
        Returns:
            List of Message objects read from the buffer
        """
        # Read and clear file asynchronously
        messages = await asyncio.to_thread(self._flush_sync)
        return messages
    
    def _flush_sync(self) -> List[Message]:
        """Synchronous helper for reading and clearing buffer."""
        messages = []
        
        # Check if file exists
        if not os.path.exists(self.buffer_file):
            return messages
        
        try:
            # Read all lines from file
            with open(self.buffer_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Parse each line as a Message
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    msg_dict = json.loads(line)
                    
                    # Reconstruct Message object
                    message = Message(
                        id=msg_dict["id"],
                        timestamp=datetime.fromisoformat(msg_dict["timestamp"]),
                        source_ip=msg_dict["source_ip"],
                        message_type=MessageType(msg_dict["message_type"]),
                        severity=Severity(msg_dict["severity"]),
                        payload=msg_dict["payload"],
                        metadata=msg_dict.get("metadata", {})
                    )
                    messages.append(message)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    # Log error but continue processing other messages
                    print(f"Error parsing buffer line: {e}, line: {line[:100]}")
            
            # Clear the file by truncating
            with open(self.buffer_file, "w", encoding="utf-8") as f:
                f.truncate(0)
                
        except IOError as e:
            print(f"Error reading buffer file: {e}")
        
        return messages
