"""
Message data models for the Mutt log processing system.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Dict, Any


class MessageType(Enum):
    """Enumeration of supported message types."""
    SYSLOG = "SYSLOG"
    SNMP_TRAP = "SNMP_TRAP"
    UNKNOWN = "UNKNOWN"


class Severity(Enum):
    """Enumeration of message severity levels."""
    EMERGENCY = "EMERGENCY"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    INFO = "INFO"
    DEBUG = "DEBUG"


@dataclass
class Message:
    """
    Base class for all message types.
    
    Attributes:
        id: Unique identifier (UUIDv4)
        timestamp: UTC timestamp when message was received
        source_ip: Source IP address
        message_type: Type of message
        severity: Severity level
        payload: Raw text content
        metadata: Additional fields as key-value pairs
    """
    source_ip: str
    message_type: MessageType
    severity: Severity
    payload: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyslogMessage(Message):
    """
    Syslog-specific message.
    
    Attributes:
        facility: Syslog facility code
        priority: Syslog priority value
        hostname: Hostname parsed from syslog header
        process_name: Name of the process that generated the message
        process_id: PID of the process that generated the message
    """
    facility: int = 0
    priority: int = 0
    hostname: str = ""
    process_name: Optional[str] = None
    process_id: Optional[int] = None


@dataclass
class SNMPTrap(Message):
    """
    SNMP trap message.
    
    Attributes:
        oid: Trap Object Identifier
        varbinds: Key-value pairs of trap data
        version: SNMP version (e.g., 'v2c', 'v3')
    """
    oid: str = ""
    varbinds: Dict[str, Any] = field(default_factory=dict)
    version: str = "v2c"