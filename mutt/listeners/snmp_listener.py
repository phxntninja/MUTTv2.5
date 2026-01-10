"""
SNMP listener implementation for Mutt.
Listens for SNMP traps over UDP.
"""

import asyncio
import logging
from typing import Optional, Tuple, Dict, Any

from mutt.listeners.base import BaseListener
from mutt.models.message import MessageType, Severity, SNMPTrap

logger = logging.getLogger(__name__)

class SNMPProtocol(asyncio.DatagramProtocol):
    """Protocol handler for SNMP UDP datagrams."""
    
    def __init__(self, listener: 'SNMPListener'):
        self.listener = listener
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Called when a datagram is received."""
        self.listener.process_data(data, addr)


class SNMPListener(BaseListener):
    """
    Listener for SNMP traps over UDP.
    
    Currently implements a stubbed version that binds to the port
    and creates SNMPTrap objects with raw data.
    """
    
    def __init__(
        self,
        queue: asyncio.Queue,
        port: int = 5162,
        host: str = "0.0.0.0"
    ):
        """
        Initialize the SNMP listener.
        
        Args:
            queue: Queue to put parsed messages into
            port: UDP port to listen on (default: 5162)
            host: Host interface to bind to (default: "0.0.0.0")
        """
        super().__init__(queue)
        self.port = port
        self.host = host
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional[SNMPProtocol] = None
        
    async def start(self) -> None:
        """Start listening for SNMP traps."""
        loop = asyncio.get_running_loop()
        self.protocol = SNMPProtocol(self)
        
        # Create UDP endpoint
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self.protocol,
            local_addr=(self.host, self.port)
        )
        self._is_running = True
        logger.info(f"SNMP listener started on {self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop the listener and clean up resources."""
        if self.transport:
            self.transport.close()
            self.transport = None
            self.protocol = None
            self._is_running = False
            logger.info("SNMP listener stopped")
    
    def process_data(self, data: bytes, addr: Tuple[str, int]) -> None:
        """
        Process incoming SNMP data.
        
        Args:
            data: Raw UDP payload
            addr: Tuple of (source_ip, source_port)
        """
        try:
            source_ip, _ = addr
            
            # Stubbed parsing: Create SNMPTrap with raw data
            trap = SNMPTrap(
                source_ip=source_ip,
                message_type=MessageType.SNMP_TRAP,
                severity=Severity.INFO,
                payload="SNMP Trap Received (Parsing pending)",
                oid="1.3.6.1.4.1",
                varbinds={"raw_data": data.hex()},
                version="v2c"
            )
            
            # Put the message in the queue
            self.queue.put_nowait(trap)
                
        except Exception as e:
            logger.error(f"Error processing SNMP data: {e}")
