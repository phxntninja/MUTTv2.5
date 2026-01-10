"""
Syslog listener implementation for Mutt.
Listens for syslog messages over UDP and parses them into SyslogMessage objects.
"""

import asyncio
import re
import logging
from typing import Optional, Tuple

from mutt.listeners.base import BaseListener
from mutt.models.message import MessageType, Severity, SyslogMessage

logger = logging.getLogger(__name__)

class SyslogProtocol(asyncio.DatagramProtocol):
    """Protocol handler for syslog UDP datagrams."""
    
    def __init__(self, listener: 'SyslogListener'):
        self.listener = listener
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Called when a datagram is received."""
        self.listener.process_data(data, addr)


class SyslogListener(BaseListener):
    """
    Listener for syslog messages over UDP.
    
    Parses syslog messages according to RFC 3164 format and converts them
    to SyslogMessage objects for processing.
    """
    
    # RFC 3164 syslog format regex
    # <PRI>TIMESTAMP HOSTNAME TAG: MESSAGE
    SYSLOG_REGEX = re.compile(
        r'<(\d+)>(\w{3}\s+\d+\s+\d+:\d+:\d+)\s+([\w\.-]+)\s+([^:]+):\s*(.*)',
        re.DOTALL
    )
    
    # Map syslog severity numbers to Severity enum
    SEVERITY_MAP = {
        0: Severity.EMERGENCY,
        1: Severity.ALERT,
        2: Severity.CRITICAL,
        3: Severity.ERROR,
        4: Severity.WARNING,
        5: Severity.NOTICE,
        6: Severity.INFO,
        7: Severity.DEBUG,
    }
    
    def __init__(
        self,
        queue: asyncio.Queue,
        port: int = 5514,
        host: str = "0.0.0.0"
    ):
        """
        Initialize the syslog listener.
        
        Args:
            queue: Queue to put parsed messages into
            port: UDP port to listen on (default: 5514)
            host: Host interface to bind to (default: "0.0.0.0")
        """
        super().__init__(queue)
        self.port = port
        self.host = host
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional[SyslogProtocol] = None
        
    async def start(self) -> None:
        """Start listening for syslog messages."""
        loop = asyncio.get_running_loop()
        self.protocol = SyslogProtocol(self)
        
        # Create UDP endpoint
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self.protocol,
            local_addr=(self.host, self.port)
        )
        self._is_running = True
        logger.info(f"Syslog listener started on {self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop the listener and clean up resources."""
        if self.transport:
            self.transport.close()
            self.transport = None
            self.protocol = None
            self._is_running = False
            logger.info("Syslog listener stopped")
    
    def process_data(self, data: bytes, addr: Tuple[str, int]) -> None:
        """
        Process incoming syslog data.
        
        Args:
            data: Raw UDP payload
            addr: Tuple of (source_ip, source_port)
        """
        try:
            # Decode the data
            text = data.decode('utf-8', errors='replace').strip()
            source_ip, source_port = addr
            
            # Parse the syslog message
            syslog_msg = self._parse_syslog_message(text, source_ip)
            
            if syslog_msg:
                # Put the message in the queue
                self.queue.put_nowait(syslog_msg)
                
        except Exception as e:
            logger.error(f"Error processing syslog data: {e}")
    
    def _parse_syslog_message(
        self, 
        text: str, 
        source_ip: str
    ) -> Optional[SyslogMessage]:
        """
        Parse a syslog message string into a SyslogMessage object.
        
        Args:
            text: Raw syslog message text
            source_ip: Source IP address
            
        Returns:
            SyslogMessage object if parsing successful, None otherwise
        """
        try:
            match = self.SYSLOG_REGEX.match(text)
            
            if match:
                # Parse structured syslog message
                priority_str, timestamp, hostname, process_name, payload = match.groups()
                
                # Parse priority
                priority = int(priority_str)
                facility = priority // 8
                severity_num = priority % 8
                
                # Map severity number to Severity enum
                severity = self.SEVERITY_MAP.get(severity_num, Severity.INFO)
                
            else:
                # Unstructured message - use defaults
                priority = 13  # Default: user-level, notice (1*8 + 5)
                facility = 1  # user-level
                severity_num = 5  # notice
                severity = Severity.INFO  # Default for unknown format
                hostname = "unknown"
                process_name = "unknown"
                payload = text
            
            # Create and return the syslog message
            return SyslogMessage(
                source_ip=source_ip,
                message_type=MessageType.SYSLOG,
                severity=severity,
                payload=payload,
                facility=facility,
                priority=priority,
                hostname=hostname,
                process_name=process_name
            )
            
        except Exception as e:
            logger.error(f"Failed to parse syslog message: {e}")
            return None
