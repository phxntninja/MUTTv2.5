"""
Message enrichment processor.
Handles reverse DNS lookups, device registry updates, and severity normalization.
"""

import socket
import logging
import asyncio
from typing import Optional

from mutt.models.message import Message, Severity
from mutt.storage.device_registry import DeviceRegistry

logger = logging.getLogger(__name__)


class Enricher:
    """Enriches messages with additional metadata and normalizes fields."""
    
    def __init__(self, registry: DeviceRegistry):
        """
        Initialize the Enricher.
        
        Args:
            registry: Device registry for tracking devices
        """
        self.registry = registry
    
    async def enrich(self, msg: Message) -> None:
        """
        Enrich a message with additional metadata and normalize fields.
        
        Performs:
        1. Reverse DNS lookup for source IP
        2. Device registry update
        3. Severity normalization
        
        Args:
            msg: Message to enrich
        """
        # Perform reverse DNS lookup
        hostname = await self._reverse_dns_lookup(msg.source_ip)
        
        # Update metadata if hostname found
        if hostname:
            msg.metadata["hostname"] = hostname
        
        # Update device registry
        await self._update_device_registry(msg.source_ip, hostname)
        
        # Normalize severity
        self._normalize_severity(msg)
    
    async def _reverse_dns_lookup(self, ip_address: str) -> Optional[str]:
        """
        Perform reverse DNS lookup for an IP address.
        
        Args:
            ip_address: IP address to look up
            
        Returns:
            Hostname if found, None otherwise
        """
        if not ip_address:
            return None
            
        try:
            # Run reverse DNS lookup in thread pool to avoid blocking
            hostname, _, _ = await asyncio.to_thread(socket.gethostbyaddr, ip_address)
            logger.debug(f"Reverse DNS lookup successful for {ip_address}: {hostname}")
            return hostname
        except (socket.herror, socket.gaierror, Exception) as e:
            logger.debug(f"Reverse DNS lookup failed for {ip_address}: {e}")
            return None
    
    async def _update_device_registry(self, ip_address: str, hostname: Optional[str]) -> None:
        """
        Update device registry with IP and hostname information.
        
        Args:
            ip_address: Device IP address
            hostname: Device hostname (optional)
        """
        try:
            await self.registry.update_device(ip_address, hostname=hostname)
            logger.debug(f"Updated device registry for {ip_address}")
        except Exception as e:
            logger.warning(f"Failed to update device registry for {ip_address}: {e}")
    
    def _normalize_severity(self, msg: Message) -> None:
        """
        Normalize message severity to Severity enum.
        
        Args:
            msg: Message to normalize
        """
        if isinstance(msg.severity, Severity):
            # Already a Severity enum, nothing to do
            return
        
        if isinstance(msg.severity, str):
            try:
                # Try to convert string to Severity enum
                severity_str = msg.severity.upper()
                msg.severity = Severity[severity_str]
            except KeyError:
                # If string doesn't match any Severity enum, default to INFO
                logger.warning(f"Unknown severity string '{msg.severity}', defaulting to INFO")
                msg.severity = Severity.INFO
        else:
            # For any other type, default to INFO
            logger.warning(f"Invalid severity type {type(msg.severity)}, defaulting to INFO")
            msg.severity = Severity.INFO
