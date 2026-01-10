# MUTT - Multi-Use Telemetry Tool
## Comprehensive Architectural Design Document

**Version**: 2.0  
**Date**: January 2026  
**Status**: Design Phase - Ready for Implementation  
**Target Python Version**: 3.9.6+

---

## 1. Executive Summary

MUTT is an async-first network monitoring ingestion and processing system designed to:
- Ingest SNMP traps (port 5162 UDP) and syslog messages (port 5514 UDP/TCP)
- Process messages at ~9,000 msg/min through an async queue
- Match messages against pattern rules
- Route matched alerts to external webhooks (future) or local SQLite database (current)
- Display messages via a separate web UI that reads from SQLite

**Key Design Principles**:
- Async-first with `asyncio` standard library
- Modular architecture with single responsibility per component
- Separation of concerns (MUTT core separate from web UI)
- No message loss during high-volume spikes (file buffering safeguard)
- YAML configuration for simplicity
- SQLite with `aiosqlite` for async database operations

---

## 2. System Architecture Overview

```
NETWORK DEVICES
    ↓
    ├─→ SNMP Traps (port 5162 UDP)
    └─→ Syslog Messages (port 5514 UDP/TCP)
    
MUTT DAEMON (mutt_daemon.py)
    ├─→ SNMPListener (async task)
    ├─→ SyslogListener (async task)
    └─→ MessageProcessor (async task)
        ├─→ Validator
        ├─→ PatternMatcher
        ├─→ Enricher
        └─→ DatabaseWriter (aiosqlite)
    
OUTPUT LAYER
    ├─→ SQLite Database (messages.db)
    └─→ File Buffer (overflow.jsonl)
    
WEB UI (separate codebase)
    └─→ Reads from SQLite, displays to browser
```

---

## 3. Project Structure

```
mutt_home/
├── mutt/
│   ├── __init__.py
│   ├── daemon.py                 # Main entry point
│   ├── config.py                 # Config loading (YAML → dataclasses)
│   ├── logger.py                 # Logging setup
│   ├── listeners/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract listener base class
│   │   ├── snmp_listener.py      # SNMP trap listener
│   │   └── syslog_listener.py    # Syslog listener
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── message_processor.py  # Main processor orchestrator
│   │   ├── validator.py          # Message validation
│   │   ├── pattern_matcher.py    # Pattern matching against rules
│   │   ├── enricher.py           # Message enrichment
│   │   └── message_router.py     # Message routing to outputs
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py           # aiosqlite wrapper
│   │   ├── device_registry.py    # Device tracking and inventory
│   │   ├── archive_manager.py    # Message archiving to CSV/JSONL
│   │   ├── buffer.py             # File buffering for overflow
│   │   └── schema.py             # Database schema definitions
│   ├── models/
│   │   ├── __init__.py
│   │   ├── message.py            # Message dataclasses
│   │   ├── credentials.py        # Credential dataclasses
│   │   └── rules.py              # Alert rule dataclasses
│   └── utils/
│       ├── __init__.py
│       └── helpers.py            # Shared utilities
├── config/
│   ├── mutt_config.yaml          # Main configuration file
│   └── alert_rules.yaml          # Pattern matching rules
├── tests/
│   ├── __init__.py
│   ├── test_listeners.py
│   ├── test_processor.py
│   └── test_database.py
├── requirements.txt
├── README.md
└── run.sh                        # Startup script
```

---

## 4. Configuration (YAML-based)

### File: `config/mutt_config.yaml`

```yaml
# MUTT Configuration

daemon:
  log_level: INFO
  log_file: ./logs/mutt.log
  pid_file: ./mutt.pid

listeners:
  snmp:
    enabled: true
    port: 5162
    protocol: udp
    buffer_size: 65535
    
  syslog:
    enabled: true
    port: 5514
    protocol: udp  # or tcp
    buffer_size: 65535

processor:
  queue_max_size: 10000       # Max items before file buffering
  batch_write_size: 100       # Write to DB in batches
  batch_timeout_seconds: 5    # Max wait for batch

storage:
  database:
    path: ./data/messages.db
    connection_timeout: 30
  
  file_buffer:
    enabled: true
    path: ./data/overflow.jsonl
    max_size_mb: 500           # Auto-clear when exceeded
  
  archiver:
    enabled: true
    path: ./data/archives
    format: csv                # csv or jsonl
    size_threshold_mb: 500     # Archive when DB exceeds this
    time_threshold_days: 7     # Or archive every N days
    compress: false            # Future: gzip compression option

pattern_matching:
  rules_file: ./config/alert_rules.yaml
  reload_interval_seconds: 300  # Reload rules every 5 min
```

### File: `config/alert_rules.yaml`

```yaml
# Alert Pattern Rules

rules:
  - id: "rule_001"
    name: "High Temperature Alert"
    pattern_type: "regex"
    pattern: "temperature.*critical"
    severity: "critical"
    action: "webhook"
    
  - id: "rule_002"
    name: "Interface Down"
    pattern_type: "keyword"
    keywords: ["down", "unreachable"]
    severity: "warning"
    action: "webhook"
    
  - id: "rule_003"
    name: "Memory Low"
    pattern_type: "regex"
    pattern: "memory.*low|low.*memory"
    severity: "info"
    action: "store"
```

### File: `config/snmpv3_credentials.yaml`

```yaml
# SNMPv3 Credentials by Username
# Supports credential rotation: add new creds with active: false, then activate later

snmpv3_credentials:
  - username: snmpuser
    credentials:
      - priority: 1
        auth_type: SHA
        auth_password: authpass123
        priv_type: AES
        priv_password: privpass456
        active: true
      - priority: 2
        auth_type: SHA
        auth_password: authpass_new
        priv_type: AES
        priv_password: privpass_new
        active: false
        
  - username: otheruser
    credentials:
      - priority: 1
        auth_type: MD5
        auth_password: authpass789
        priv_type: DES
        priv_password: privpass000
        active: true
```

---

## 5A. Credential Loader (config.py)

**File**: `mutt/config.py`

```python
import yaml
from typing import Dict, List
from mutt.models.credentials import SNMPv3CredentialSet, SNMPv3Credential

class ConfigLoader:
    """Loads YAML configuration files"""
    
    @staticmethod
    def load_config(config_path: str) -> dict:
        """Load main configuration from YAML"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"[ConfigLoader] Error loading config {config_path}: {e}")
            raise

class CredentialLoader:
    """Loads SNMPv3 credentials from YAML"""
    
    @staticmethod
    def load_credentials(credentials_path: str) -> Dict[str, SNMPv3CredentialSet]:
        """
        Load SNMPv3 credentials from YAML file.
        Returns dict keyed by username.
        """
        try:
            with open(credentials_path, 'r') as f:
                data = yaml.safe_load(f)
            
            credentials_dict = {}
            
            for cred_set in data.get('snmpv3_credentials', []):
                username = cred_set['username']
                
                # Parse individual credentials
                creds_list = []
                for cred_data in cred_set.get('credentials', []):
                    cred = SNMPv3Credential(
                        priority=cred_data['priority'],
                        auth_type=cred_data['auth_type'],
                        auth_password=cred_data['auth_password'],
                        priv_type=cred_data['priv_type'],
                        priv_password=cred_data['priv_password'],
                        active=cred_data.get('active', True)
                    )
                    creds_list.append(cred)
                
                # Create credential set and sort by priority
                cred_set_obj = SNMPv3CredentialSet(
                    username=username,
                    credentials=sorted(creds_list, key=lambda x: x.priority)
                )
                
                credentials_dict[username] = cred_set_obj
                print(f"[CredentialLoader] Loaded credentials for user: {username}")
            
            return credentials_dict
            
        except Exception as e:
            print(f"[CredentialLoader] Error loading credentials: {e}")
            return {}
```

---

## 5. Data Models (Dataclasses)

### File: `mutt/models/message.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

class MessageType(Enum):
    SNMP_TRAP = "snmp_trap"
    SYSLOG = "syslog"

class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"

@dataclass
class Message:
    """Core message object passed through MUTT pipeline"""
    id: str                           # Unique message ID (UUID)
    type: MessageType
    source_ip: str
    source_device: str                # Hostname or device name
    timestamp: datetime
    raw_message: str                  # Original message content
    
    # Processing metadata
    received_at: datetime = field(default_factory=datetime.utcnow)
    validated: bool = False
    validation_errors: list[str] = field(default_factory=list)
    
    # Pattern matching results
    matched_rule_id: Optional[str] = None
    matched_rule_name: Optional[str] = None
    match_severity: Optional[Severity] = None
    
    # Enrichment data
    enriched_data: Dict[str, Any] = field(default_factory=dict)
    
    # Storage status
    stored_to_db: bool = False
    stored_to_buffer: bool = False
    error_message: Optional[str] = None

@dataclass
class SNMPTrap(Message):
    """SNMP-specific message fields"""
    oid: str = ""
    trap_type: str = ""
    snmp_version: str = "v2c"
    community_string: Optional[str] = None

@dataclass
class SyslogMessage(Message):
    """Syslog-specific message fields"""
    facility: str = ""
    level: int = 0
    program: str = ""
    process_id: Optional[int] = None
    tag: str = ""
```

### File: `mutt/models/rules.py`

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

class PatternType(Enum):
    REGEX = "regex"
    KEYWORD = "keyword"
    EXACT = "exact"

class ActionType(Enum):
    WEBHOOK = "webhook"
    STORE = "store"
    DISCARD = "discard"

@dataclass
class AlertRule:
    """Pattern matching rule"""
    id: str
    name: str
    pattern_type: PatternType
    pattern: Optional[str] = None              # For regex/exact
    keywords: Optional[List[str]] = None       # For keyword matching
    severity: str = "info"
    action: ActionType = ActionType.STORE
    enabled: bool = True
```

### File: `mutt/models/credentials.py`

```python
from dataclasses import dataclass
from typing import List

@dataclass
class SNMPv3Credential:
    """Single SNMPv3 credential set (auth/priv pair)"""
    priority: int                           # Lower number = higher priority
    auth_type: str                          # SHA, MD5, etc.
    auth_password: str
    priv_type: str                          # AES, DES, etc.
    priv_password: str
    active: bool = True

@dataclass
class SNMPv3CredentialSet:
    """Collection of credentials for a single username"""
    username: str
    credentials: List[SNMPv3Credential]     # Sorted by priority
    
    def get_active_credentials(self) -> List[SNMPv3Credential]:
        """Return active credentials sorted by priority"""
        return sorted(
            [c for c in self.credentials if c.active],
            key=lambda x: x.priority
        )
```

---

## 6. Component Design

### 6.1 Listener Base Class

**File**: `mutt/listeners/base.py`

```python
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from mutt.models.message import Message

class BaseListener(ABC):
    """Abstract base for all message listeners"""
    
    def __init__(self, queue: asyncio.Queue, config: dict):
        self.queue = queue
        self.config = config
        self.running = False
        self.message_count = 0
    
    @abstractmethod
    async def listen(self):
        """Main listening loop - implemented by subclasses"""
        pass
    
    @abstractmethod
    async def parse_message(self, raw_data: bytes, source_ip: str) -> Optional[Message]:
        """Parse raw network data into Message object"""
        pass
    
    async def enqueue_message(self, message: Message):
        """Add validated message to queue"""
        try:
            await self.queue.put(message)
            self.message_count += 1
            if self.message_count % 100 == 0:
                print(f"[{self.__class__.__name__}] Enqueued {self.message_count} messages")
        except Exception as e:
            print(f"[{self.__class__.__name__}] Queue error: {e}")
    
    async def start(self):
        """Start listener task"""
        self.running = True
        try:
            await self.listen()
        except Exception as e:
            print(f"[{self.__class__.__name__}] Fatal error: {e}")
            self.running = False
```

### 6.2 SNMP Listener

**File**: `mutt/listeners/snmp_listener.py`

```python
import asyncio
import uuid
from datetime import datetime
from typing import Optional
from pysnmp.hlapi.asyncio import *
from pysnmp.smi import builder, view

from mutt.models.message import Message, SNMPTrap, MessageType
from mutt.listeners.base import BaseListener

class SNMPListener(BaseListener):
    """Receives SNMP traps on port 5162"""
    
    def __init__(self, queue: asyncio.Queue, config: dict):
        super().__init__(queue, config)
        self.port = config.get('snmp', {}).get('port', 5162)
        self.buffer_size = config.get('snmp', {}).get('buffer_size', 65535)
        
        # MIB handling for OID translation
        self.mib_builder = builder.MibBuilder()
        self.mib_view = view.MibViewController(self.mib_builder)
    
    async def listen(self):
        """Listen for SNMP traps on configured port"""
        # Using pysnmp's async SNMP engine
        snmp_engine = SnmpEngine()
        config = snmp_engine.getContext('snmpContext')
        
        # Configure SNMPv2c community string (default, can be overridden)
        snmp_engine.getContext('snmpContext').communityData.update(
            CommunityData('public', mpModel=1)
        )
        
        # Setup trap receiver
        trapCtx = config
        
        async def trapReceived(snmpEngine, stateReference, contextEngineId, 
                               contextName, varBinds, cbCtx):
            """Callback for received SNMP trap"""
            peer = snmpEngine.getTransportDispatcher().getConnection(stateReference)
            source_ip = peer[0]
            
            # Parse trap data
            message = await self.parse_message(varBinds, source_ip)
            if message:
                await self.enqueue_message(message)
        
        # Register trap receiver
        config.notificationReceiver(
            ('0.0.0.0', self.port),
            trapReceived
        )
        
        # Main event loop
        while self.running:
            await asyncio.sleep(0.1)
    
    async def parse_message(self, trap_data: tuple, source_ip: str) -> Optional[SNMPTrap]:
        """Parse SNMP trap into Message object"""
        try:
            # Extract OID, type, values from trap_data
            oid = str(trap_data[0][0]) if trap_data else "unknown"
            
            message = SNMPTrap(
                id=str(uuid.uuid4()),
                type=MessageType.SNMP_TRAP,
                source_ip=source_ip,
                source_device=source_ip,  # Will be enriched later
                timestamp=datetime.utcnow(),
                raw_message=str(trap_data),
                oid=oid,
                snmp_version="v2c"
            )
            return message
        except Exception as e:
            print(f"[SNMPListener] Parse error: {e}")
            return None
```

### 6.3 Syslog Listener

**File**: `mutt/listeners/syslog_listener.py`

```python
import asyncio
import uuid
import re
from datetime import datetime
from typing import Optional

from mutt.models.message import Message, SyslogMessage, MessageType
from mutt.listeners.base import BaseListener

class SyslogListener(BaseListener):
    """Receives syslog messages on port 5514"""
    
    def __init__(self, queue: asyncio.Queue, config: dict):
        super().__init__(queue, config)
        self.port = config.get('syslog', {}).get('port', 5514)
        self.protocol = config.get('syslog', {}).get('protocol', 'udp')
        self.buffer_size = config.get('syslog', {}).get('buffer_size', 65535)
        
        # RFC 3164 syslog format regex
        self.syslog_regex = re.compile(
            r'<(\d+)>(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s*(.*)'
        )
    
    async def listen(self):
        """Listen for syslog messages on configured port"""
        if self.protocol == 'udp':
            await self._listen_udp()
        else:
            await self._listen_tcp()
    
    async def _listen_udp(self):
        """UDP listener"""
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: SyslogUDPProtocol(self),
            local_addr=('0.0.0.0', self.port)
        )
        
        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            transport.close()
    
    async def _listen_tcp(self):
        """TCP listener"""
        server = await asyncio.start_server(
            self._handle_tcp_connection,
            '0.0.0.0',
            self.port
        )
        
        async with server:
            while self.running:
                await asyncio.sleep(1)
    
    async def _handle_tcp_connection(self, reader, writer):
        """Handle individual TCP syslog connection"""
        try:
            while self.running:
                data = await reader.read(self.buffer_size)
                if not data:
                    break
                
                peer = writer.get_extra_info('peername')
                source_ip = peer[0] if peer else 'unknown'
                
                message = await self.parse_message(data, source_ip)
                if message:
                    await self.enqueue_message(message)
        except Exception as e:
            print(f"[SyslogListener] TCP error: {e}")
        finally:
            writer.close()
    
    async def parse_message(self, raw_data: bytes, source_ip: str) -> Optional[SyslogMessage]:
        """Parse syslog message into Message object"""
        try:
            raw_text = raw_data.decode('utf-8', errors='replace').strip()
            
            # Parse priority (facility + severity)
            match = self.syslog_regex.match(raw_text)
            if match:
                priority, timestamp, hostname, program, pid, message_text = match.groups()
                priority = int(priority)
                facility = priority // 8
                level = priority % 8
            else:
                # Fallback for unparseable messages
                facility = 16  # local0
                level = 6      # info
                hostname = source_ip
                program = 'unknown'
                pid = None
                message_text = raw_text
            
            message = SyslogMessage(
                id=str(uuid.uuid4()),
                type=MessageType.SYSLOG,
                source_ip=source_ip,
                source_device=hostname,
                timestamp=datetime.utcnow(),
                raw_message=raw_text,
                facility=str(facility),
                level=level,
                program=program,
                process_id=int(pid) if pid else None,
                tag=f"{program}[{pid}]" if pid else program
            )
            return message
        except Exception as e:
            print(f"[SyslogListener] Parse error: {e}")
            return None

class SyslogUDPProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for syslog"""
    
    def __init__(self, listener: SyslogListener):
        self.listener = listener
    
    def datagram_received(self, data: bytes, addr: tuple):
        """Called when UDP datagram is received"""
        source_ip = addr[0]
        asyncio.create_task(
            self.listener.parse_and_enqueue(data, source_ip)
        )
    
    def error_received(self, exc):
        print(f"[SyslogUDPProtocol] Error: {exc}")
```

### 6.4 Message Processor

**File**: `mutt/processors/message_processor.py`

```python
import asyncio
import json
from datetime import datetime
from typing import List

from mutt.models.message import Message
from mutt.processors.validator import Validator
from mutt.processors.pattern_matcher import PatternMatcher
from mutt.processors.enricher import Enricher
from mutt.processors.message_router import MessageRouter
from mutt.storage.database import Database
from mutt.storage.device_registry import DeviceRegistry
from mutt.storage.archive_manager import ArchiveManager
from mutt.storage.buffer import FileBuffer

class MessageProcessor:
    """Main orchestrator for message processing pipeline"""
    
    def __init__(self, config: dict):
        self.config = config
        self.queue: asyncio.Queue = asyncio.Queue(
            maxsize=config['processor'].get('queue_max_size', 10000)
        )
        
        self.database = Database(config)
        self.device_registry = DeviceRegistry(self.database)
        self.archive_manager = ArchiveManager(config, self.database)
        self.file_buffer = FileBuffer(config)
        
        self.validator = Validator(config)
        self.pattern_matcher = PatternMatcher(config)
        self.enricher = Enricher(config, self.device_registry)
        self.router = MessageRouter(config)
        
        self.batch_write_size = config['processor'].get('batch_write_size', 100)
        self.batch_timeout = config['processor'].get('batch_timeout_seconds', 5)
        
        self.running = False
        self.processed_count = 0
        self.batch = []
        self.last_batch_time = datetime.utcnow()
    
    async def start(self):
        """Start the message processing pipeline"""
        self.running = True
        await self.database.initialize()
        
        # Register output handlers with router
        self._register_handlers()
        
        # Start three concurrent tasks:
        # 1. Dequeue and process messages
        # 2. Periodic batch writes to database
        # 3. Periodic archive checks
        await asyncio.gather(
            self._process_loop(),
            self._batch_write_loop(),
            self._archive_check_loop()
        )
    
    def _register_handlers(self):
        """Register output handlers for message router"""
        from mutt.models.rules import ActionType
        
        # STORE action: add message to batch for database write
        async def store_handler(message: Message):
            self.batch.append(message)
            if len(self.batch) >= self.batch_write_size:
                await self._flush_batch()
        
        self.router.register_handler(ActionType.STORE, store_handler)
        
        # WEBHOOK action: placeholder for future webhook implementation
        async def webhook_handler(message: Message):
            print(f"[MessageProcessor] Webhook handler (not yet implemented): {message.id}")
            # Future: Send to external webhook/API
            # For now, also store to database as fallback
            self.batch.append(message)
        
        self.router.register_handler(ActionType.WEBHOOK, webhook_handler)
        
        # DISCARD action: do nothing (no storage)
        async def discard_handler(message: Message):
            print(f"[MessageProcessor] Discarding message: {message.id}")
        
        self.router.register_handler(ActionType.DISCARD, discard_handler)
    
    async def _process_loop(self):
        """Main processing loop - dequeue and validate/match/enrich/route"""
        while self.running:
            try:
                message = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0
                )
                
                # Validation
                await self.validator.validate(message)
                
                # Pattern matching
                await self.pattern_matcher.match(message)
                
                # Enrichment
                await self.enricher.enrich(message)
                
                # Route to appropriate output(s)
                await self.router.route(message)
                
                self.processed_count += 1
                
                if self.processed_count % 100 == 0:
                    print(f"[MessageProcessor] Processed {self.processed_count} messages")
                
                # Flush batch if size exceeded
                if len(self.batch) >= self.batch_write_size:
                    await self._flush_batch()
                
            except asyncio.TimeoutError:
                # No message available, check if batch needs flushing
                if self.batch and self._batch_timeout_exceeded():
                    await self._flush_batch()
            except Exception as e:
                print(f"[MessageProcessor] Processing error: {e}")
    
    async def _batch_write_loop(self):
        """Periodic batch write to database"""
        while self.running:
            await asyncio.sleep(self.batch_timeout)
            if self.batch and self._batch_timeout_exceeded():
                await self._flush_batch()
    
    async def _archive_check_loop(self):
        """Periodic check for archiving old messages"""
        archive_check_interval = 300  # Check every 5 minutes
        
        while self.running:
            try:
                await asyncio.sleep(archive_check_interval)
                await self.archive_manager.check_and_archive()
            except Exception as e:
                print(f"[MessageProcessor] Archive check error: {e}")
    
    async def _flush_batch(self):
        """Write accumulated batch to database"""
        if not self.batch:
            return
        
        try:
            # Try to write to database
            await self.database.write_messages(self.batch)
            
            # Mark as stored
            for msg in self.batch:
                msg.stored_to_db = True
            
            print(f"[MessageProcessor] Batch write: {len(self.batch)} messages")
            self.batch = []
            self.last_batch_time = datetime.utcnow()
            
        except Exception as e:
            print(f"[MessageProcessor] Database write failed: {e}")
            
            # Fallback to file buffer
            try:
                await self.file_buffer.write_messages(self.batch)
                for msg in self.batch:
                    msg.stored_to_buffer = True
                print(f"[MessageProcessor] Fallback: wrote {len(self.batch)} to file buffer")
                self.batch = []
            except Exception as buffer_error:
                print(f"[MessageProcessor] File buffer also failed: {buffer_error}")
                # Messages remain in batch for retry
    
    def _batch_timeout_exceeded(self) -> bool:
        """Check if batch timeout has been exceeded"""
        elapsed = (datetime.utcnow() - self.last_batch_time).total_seconds()
        return elapsed >= self.batch_timeout
    
    async def stop(self):
        """Gracefully shutdown processor"""
        self.running = False
        # Flush any remaining batch
        if self.batch:
            await self._flush_batch()
        await self.database.close()
```

### 6.5 Validator

**File**: `mutt/processors/validator.py`

```python
from mutt.models.message import Message, MessageType

class Validator:
    """Message validation logic"""
    
    def __init__(self, config: dict):
        self.config = config
    
    async def validate(self, message: Message) -> bool:
        """Validate message has required fields"""
        errors = []
        
        # Check required fields
        if not message.id:
            errors.append("Missing message ID")
        if not message.source_ip:
            errors.append("Missing source IP")
        if not message.raw_message:
            errors.append("Missing raw message content")
        if not message.type:
            errors.append("Missing message type")
        
        # Type-specific validation
        if message.type == MessageType.SNMP_TRAP:
            if not hasattr(message, 'oid') or not message.oid:
                errors.append("SNMP trap missing OID")
        elif message.type == MessageType.SYSLOG:
            if not hasattr(message, 'program') or not message.program:
                errors.append("Syslog message missing program")
        
        if errors:
            message.validated = False
            message.validation_errors = errors
            print(f"[Validator] {message.id}: {', '.join(errors)}")
        else:
            message.validated = True
        
        return message.validated
```

### 6.6 Pattern Matcher

**File**: `mutt/processors/pattern_matcher.py`

```python
import re
import yaml
from typing import Optional

from mutt.models.message import Message
from mutt.models.rules import AlertRule, PatternType

class PatternMatcher:
    """Pattern matching against configured rules"""
    
    def __init__(self, config: dict):
        self.config = config
        self.rules: list[AlertRule] = []
        self._load_rules()
    
    def _load_rules(self):
        """Load alert rules from YAML file"""
        rules_file = self.config.get('pattern_matching', {}).get('rules_file')
        if not rules_file:
            print("[PatternMatcher] No rules file configured")
            return
        
        try:
            with open(rules_file, 'r') as f:
                rules_data = yaml.safe_load(f)
            
            self.rules = []
            for rule_dict in rules_data.get('rules', []):
                rule = AlertRule(
                    id=rule_dict['id'],
                    name=rule_dict['name'],
                    pattern_type=PatternType(rule_dict['pattern_type']),
                    pattern=rule_dict.get('pattern'),
                    keywords=rule_dict.get('keywords'),
                    severity=rule_dict.get('severity', 'info'),
                    enabled=rule_dict.get('enabled', True)
                )
                self.rules.append(rule)
            
            print(f"[PatternMatcher] Loaded {len(self.rules)} rules")
        except Exception as e:
            print(f"[PatternMatcher] Error loading rules: {e}")
    
    async def match(self, message: Message) -> bool:
        """Match message against all active rules"""
        if not message.validated:
            return False
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            if self._rule_matches(rule, message):
                message.matched_rule_id = rule.id
                message.matched_rule_name = rule.name
                message.match_severity = rule.severity
                print(f"[PatternMatcher] Message {message.id}: matched rule '{rule.name}'")
                return True
        
        return False
    
    def _rule_matches(self, rule: AlertRule, message: Message) -> bool:
        """Check if message matches a specific rule"""
        content = message.raw_message.lower()
        
        if rule.pattern_type == PatternType.REGEX:
            try:
                return bool(re.search(rule.pattern, content, re.IGNORECASE))
            except Exception as e:
                print(f"[PatternMatcher] Regex error in rule {rule.id}: {e}")
                return False
        
        elif rule.pattern_type == PatternType.KEYWORD:
            return any(kw.lower() in content for kw in rule.keywords)
        
        elif rule.pattern_type == PatternType.EXACT:
            return rule.pattern.lower() == content
        
        return False
```

### 6.7 Enricher

**File**: `mutt/processors/enricher.py`

```python
import socket
from typing import Optional

from mutt.models.message import Message, SNMPTrap, SyslogMessage
from mutt.storage.device_registry import DeviceRegistry

class Enricher:
    """Message enrichment (add metadata and track devices)"""
    
    def __init__(self, config: dict, device_registry: DeviceRegistry):
        self.config = config
        self.device_registry = device_registry
    
    async def enrich(self, message: Message):
        """Enrich message with additional metadata"""
        try:
            # Reverse DNS lookup
            hostname = await self._reverse_dns(message.source_ip)
            if hostname:
                message.source_device = hostname
            else:
                message.source_device = message.source_ip
            
            # Track device in registry
            snmp_version = None
            syslog_seen = False
            
            if isinstance(message, SNMPTrap):
                snmp_version = message.snmp_version
            elif isinstance(message, SyslogMessage):
                syslog_seen = True
            
            await self.device_registry.update_device(
                hostname=message.source_device,
                source_ip=message.source_ip,
                snmp_version=snmp_version,
                syslog_seen=syslog_seen
            )
            
            # Add processing metadata
            message.enriched_data['processing_time'] = 'N/A'  # Can calculate later
            
        except Exception as e:
            print(f"[Enricher] Error enriching message {message.id}: {e}")
    
    async def _reverse_dns(self, ip: str) -> Optional[str]:
        """Attempt reverse DNS lookup"""
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            return hostname
        except (socket.herror, socket.gaierror):
            return None
```

### 6.8 Message Router

**File**: `mutt/processors/message_router.py`

```python
from typing import Callable, Dict
from mutt.models.message import Message
from mutt.models.rules import ActionType

class MessageRouter:
    """Routes processed messages to appropriate output destinations"""
    
    def __init__(self, config: dict):
        self.config = config
        
        # Registry of output handlers (initialized by processor)
        self.handlers: Dict[ActionType, Callable] = {}
    
    def register_handler(self, action_type: ActionType, handler: Callable):
        """Register a handler for a specific action type"""
        self.handlers[action_type] = handler
        print(f"[MessageRouter] Registered handler for {action_type.value}")
    
    async def route(self, message: Message):
        """Route message based on matched rule action"""
        
        # Default action if no rule matched
        action = ActionType.STORE
        
        # If message matched a rule, use its action
        if message.matched_rule_id:
            # Get action from rule (this requires passing rule data)
            # For now, default to STORE - will be set by caller
            action = ActionType.STORE
        
        # Route to appropriate handler
        if action in self.handlers:
            handler = self.handlers[action]
            try:
                await handler(message)
            except Exception as e:
                print(f"[MessageRouter] Handler error for {action.value}: {e}")
                # Fallback: always store to database on any output failure
                if ActionType.STORE in self.handlers:
                    await self.handlers[ActionType.STORE](message)
        else:
            print(f"[MessageRouter] No handler registered for {action.value}, defaulting to STORE")
            if ActionType.STORE in self.handlers:
                await self.handlers[ActionType.STORE](message)
```

---

## 7. Storage Layer

### 7.1 Database Schema

**File**: `mutt/storage/schema.py`

```python
"""
Database schema for MUTT messages
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    hostname TEXT UNIQUE NOT NULL,
    source_ip TEXT UNIQUE NOT NULL,
    last_seen_snmp_version TEXT,
    last_seen_syslog BOOLEAN DEFAULT 0,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_device_hostname ON devices(hostname);
CREATE INDEX idx_device_ip ON devices(source_ip);
CREATE INDEX idx_device_snmp_version ON devices(last_seen_snmp_version);

CREATE TABLE IF NOT EXISTS archives (
    id TEXT PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    message_count INTEGER,
    size_bytes INTEGER,
    archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    earliest_message_timestamp DATETIME,
    latest_message_timestamp DATETIME
);

CREATE INDEX idx_archive_date ON archives(archived_at);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    source_ip TEXT NOT NULL,
    source_device TEXT,
    timestamp DATETIME NOT NULL,
    received_at DATETIME NOT NULL,
    raw_message TEXT,
    
    -- Processing metadata
    validated BOOLEAN DEFAULT 0,
    validation_errors TEXT,
    
    -- Pattern matching results
    matched_rule_id TEXT,
    matched_rule_name TEXT,
    match_severity TEXT,
    
    -- Enrichment
    enriched_data TEXT,  -- JSON
    
    -- Storage status
    stored_to_db BOOLEAN DEFAULT 0,
    stored_to_buffer BOOLEAN DEFAULT 0,
    error_message TEXT,
    
    -- Indexes
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timestamp ON messages(timestamp);
CREATE INDEX idx_source_ip ON messages(source_ip);
CREATE INDEX idx_matched_rule_id ON messages(matched_rule_id);
CREATE INDEX idx_severity ON messages(match_severity);

-- Type-specific tables for extensibility
CREATE TABLE IF NOT EXISTS snmp_messages (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    oid TEXT,
    trap_type TEXT,
    snmp_version TEXT,
    FOREIGN KEY(message_id) REFERENCES messages(id)
);

CREATE TABLE IF NOT EXISTS syslog_messages (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    facility TEXT,
    level INTEGER,
    program TEXT,
    process_id INTEGER,
    tag TEXT,
    FOREIGN KEY(message_id) REFERENCES messages(id)
);

CREATE TABLE IF NOT EXISTS snmpv3_auth_failures (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    hostname TEXT,
    num_failures INTEGER DEFAULT 1,
    last_failure DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_snmpv3_failures_username ON snmpv3_auth_failures(username);
"""
```

### 7.2 Database Wrapper

**File**: `mutt/storage/database.py`

```python
import asyncio
import json
import sqlite3
import aiosqlite
from datetime import datetime
from typing import List

from mutt.models.message import Message, SNMPTrap, SyslogMessage
from mutt.storage.schema import SCHEMA

class Database:
    """Async SQLite wrapper for message storage"""
    
    def __init__(self, config: dict):
        self.config = config
        self.db_path = config['storage']['database']['path']
        self.connection_timeout = config['storage']['database'].get('connection_timeout', 30)
        self.db: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Create database connection and initialize schema"""
        try:
            self.db = await aiosqlite.connect(
                self.db_path,
                timeout=self.connection_timeout
            )
            
            # Execute schema
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    await self.db.execute(statement)
            
            await self.db.commit()
            print(f"[Database] Initialized at {self.db_path}")
        except Exception as e:
            print(f"[Database] Initialization error: {e}")
            raise
    
    async def write_messages(self, messages: List[Message]):
        """Write batch of messages to database"""
        if not self.db:
            raise RuntimeError("Database not initialized")
        
        try:
            cursor = await self.db.cursor()
            
            for message in messages:
                # Insert into main messages table
                await cursor.execute("""
                    INSERT INTO messages (
                        id, type, source_ip, source_device, timestamp, received_at,
                        raw_message, validated, validation_errors, matched_rule_id,
                        matched_rule_name, match_severity, enriched_data,
                        stored_to_db, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.id,
                    message.type.value,
                    message.source_ip,
                    message.source_device,
                    message.timestamp.isoformat(),
                    message.received_at.isoformat(),
                    message.raw_message,
                    1 if message.validated else 0,
                    json.dumps(message.validation_errors),
                    message.matched_rule_id,
                    message.matched_rule_name,
                    message.match_severity.value if message.match_severity else None,
                    json.dumps(message.enriched_data),
                    1 if message.stored_to_db else 0,
                    message.error_message
                ))
                
                # Insert type-specific data
                if isinstance(message, SNMPTrap):
                    await cursor.execute("""
                        INSERT INTO snmp_messages (
                            id, message_id, oid, trap_type, snmp_version, community_string
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        message.id,
                        message.id,
                        message.oid,
                        message.trap_type,
                        message.snmp_version,
                        message.community_string
                    ))
                
                elif isinstance(message, SyslogMessage):
                    await cursor.execute("""
                        INSERT INTO syslog_messages (
                            id, message_id, facility, level, program, process_id, tag
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        message.id,
                        message.id,
                        message.facility,
                        message.level,
                        message.program,
                        message.process_id,
                        message.tag
                    ))
            
            await self.db.commit()
            print(f"[Database] Wrote {len(messages)} messages")
            
        except Exception as e:
            await self.db.rollback()
            print(f"[Database] Write error: {e}")
            raise
    
    async def get_messages(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """Retrieve messages from database (for web UI)"""
        if not self.db:
            raise RuntimeError("Database not initialized")
        
        try:
            cursor = await self.db.execute("""
                SELECT id, type, source_ip, source_device, timestamp, raw_message,
                       matched_rule_name, match_severity
                FROM messages
                ORDER BY received_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'type': row[1],
                    'source_ip': row[2],
                    'source_device': row[3],
                    'timestamp': row[4],
                    'message': row[5],
                    'rule': row[6],
                    'severity': row[7]
                })
            
            return results
        except Exception as e:
            print(f"[Database] Read error: {e}")
            return []
    
    async def close(self):
        """Close database connection"""
        if self.db:
            await self.db.close()
            print("[Database] Connection closed")
```

### 7.4 Device Registry

**File**: `mutt/storage/device_registry.py`

```python
import uuid
from datetime import datetime
from typing import Optional
from mutt.storage.database import Database

class DeviceRegistry:
    """Manages device inventory and tracking"""
    
    def __init__(self, database: Database):
        self.database = database
    
    async def update_device(self, hostname: str, source_ip: str, 
                           snmp_version: Optional[str] = None,
                           syslog_seen: bool = False):
        """Update or create device record"""
        if not self.database.db:
            return
        
        try:
            cursor = await self.database.db.cursor()
            
            # Check if device exists
            await cursor.execute(
                "SELECT id FROM devices WHERE hostname = ? OR source_ip = ?",
                (hostname, source_ip)
            )
            existing = await cursor.fetchone()
            
            if existing:
                # Update existing device
                update_fields = ["last_updated = CURRENT_TIMESTAMP"]
                params = []
                
                if snmp_version:
                    update_fields.append("last_seen_snmp_version = ?")
                    params.append(snmp_version)
                
                if syslog_seen:
                    update_fields.append("last_seen_syslog = 1")
                
                params.extend([hostname, source_ip])
                
                query = f"""
                    UPDATE devices 
                    SET {', '.join(update_fields)}
                    WHERE hostname = ? OR source_ip = ?
                """
                await cursor.execute(query, params)
            else:
                # Create new device
                device_id = str(uuid.uuid4())
                await cursor.execute("""
                    INSERT INTO devices (
                        id, hostname, source_ip, last_seen_snmp_version, 
                        last_seen_syslog, first_seen, last_updated
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    device_id,
                    hostname,
                    source_ip,
                    snmp_version,
                    1 if syslog_seen else 0
                ))
                
                print(f"[DeviceRegistry] New device: {hostname} ({source_ip})")
            
            await self.database.db.commit()
            
        except Exception as e:
            print(f"[DeviceRegistry] Error updating device {hostname}: {e}")
    
    async def get_device_snmp_version(self, hostname: str) -> Optional[str]:
        """Get last seen SNMP version for a device"""
        if not self.database.db:
            return None
        
        try:
            cursor = await self.database.db.cursor()
            await cursor.execute(
                "SELECT last_seen_snmp_version FROM devices WHERE hostname = ?",
                (hostname,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"[DeviceRegistry] Error fetching device {hostname}: {e}")
            return None
    
    async def get_all_devices(self):
        """Get all tracked devices"""
        if not self.database.db:
            return []
        
        try:
            cursor = await self.database.db.cursor()
            await cursor.execute("""
                SELECT id, hostname, source_ip, last_seen_snmp_version, 
                       last_seen_syslog, first_seen, last_updated
                FROM devices
                ORDER BY last_updated DESC
            """)
            
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'hostname': row[1],
                    'source_ip': row[2],
                    'snmp_version': row[3],
                    'syslog_seen': bool(row[4]),
                    'first_seen': row[5],
                    'last_updated': row[6]
                })
            
            return results
        except Exception as e:
            print(f"[DeviceRegistry] Error fetching devices: {e}")
            return []
```

### 7.5 Archive Manager

**File**: `mutt/storage/archive_manager.py`

```python
import uuid
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import json

from mutt.storage.database import Database

class ArchiveManager:
    """Manages message archiving to CSV files"""
    
    def __init__(self, config: dict, database: Database):
        self.config = config
        self.database = database
        
        self.enabled = config['storage']['archiver'].get('enabled', True)
        self.archive_path = config['storage']['archiver'].get('path', './data/archives')
        self.format = config['storage']['archiver'].get('format', 'csv')
        self.size_threshold_mb = config['storage']['archiver'].get('size_threshold_mb', 500)
        self.time_threshold_days = config['storage']['archiver'].get('time_threshold_days', 7)
        
        # Ensure archive directory exists
        Path(self.archive_path).mkdir(parents=True, exist_ok=True)
        
        self.last_archive_time = datetime.utcnow()
    
    async def check_and_archive(self) -> bool:
        """Check if archiving is needed, archive if threshold exceeded"""
        if not self.enabled or not self.database.db:
            return False
        
        # Check size threshold
        size_exceeded = await self._check_size_threshold()
        
        # Check time threshold
        time_exceeded = self._check_time_threshold()
        
        if size_exceeded or time_exceeded:
            print(f"[ArchiveManager] Archive trigger: size={size_exceeded}, time={time_exceeded}")
            return await self._archive_messages()
        
        return False
    
    async def _check_size_threshold(self) -> bool:
        """Check if database size exceeds threshold"""
        try:
            db_path = self.config['storage']['database']['path']
            if os.path.exists(db_path):
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                exceeded = size_mb >= self.size_threshold_mb
                if exceeded:
                    print(f"[ArchiveManager] DB size {size_mb:.1f}MB exceeds threshold {self.size_threshold_mb}MB")
                return exceeded
        except Exception as e:
            print(f"[ArchiveManager] Error checking DB size: {e}")
        
        return False
    
    def _check_time_threshold(self) -> bool:
        """Check if time threshold exceeded since last archive"""
        elapsed_days = (datetime.utcnow() - self.last_archive_time).days
        exceeded = elapsed_days >= self.time_threshold_days
        if exceeded:
            print(f"[ArchiveManager] Time threshold exceeded: {elapsed_days} days")
        return exceeded
    
    async def _archive_messages(self) -> bool:
        """Archive old messages to file"""
        try:
            # Get messages older than N days (keep recent messages)
            cutoff_date = datetime.utcnow() - timedelta(days=1)  # Archive messages > 1 day old
            
            messages = await self._get_messages_to_archive(cutoff_date)
            
            if not messages:
                print("[ArchiveManager] No messages to archive")
                return False
            
            # Write to archive file
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            if self.format == 'csv':
                filename = await self._write_csv(messages, timestamp)
            else:
                filename = await self._write_jsonl(messages, timestamp)
            
            # Record archive in database
            await self._record_archive(filename, messages)
            
            # Delete archived messages from database
            await self._delete_archived_messages(cutoff_date)
            
            print(f"[ArchiveManager] Archived {len(messages)} messages to {filename}")
            self.last_archive_time = datetime.utcnow()
            return True
            
        except Exception as e:
            print(f"[ArchiveManager] Archive error: {e}")
            return False
    
    async def _get_messages_to_archive(self, cutoff_date: datetime) -> List[dict]:
        """Get messages older than cutoff date"""
        if not self.database.db:
            return []
        
        try:
            cursor = await self.database.db.cursor()
            await cursor.execute("""
                SELECT id, type, source_ip, source_device, timestamp, raw_message,
                       matched_rule_id, matched_rule_name, match_severity
                FROM messages
                WHERE timestamp < ?
                ORDER BY timestamp
            """, (cutoff_date.isoformat(),))
            
            rows = await cursor.fetchall()
            
            messages = []
            for row in rows:
                messages.append({
                    'id': row[0],
                    'type': row[1],
                    'source_ip': row[2],
                    'source_device': row[3],
                    'timestamp': row[4],
                    'message': row[5],
                    'rule_id': row[6],
                    'rule_name': row[7],
                    'severity': row[8]
                })
            
            return messages
        except Exception as e:
            print(f"[ArchiveManager] Error retrieving messages: {e}")
            return []
    
    async def _write_csv(self, messages: List[dict], timestamp: str) -> str:
        """Write messages to CSV file"""
        filename = f"messages_{timestamp}.csv"
        filepath = os.path.join(self.archive_path, filename)
        
        try:
            with open(filepath, 'w', newline='') as f:
                fieldnames = [
                    'id', 'type', 'source_ip', 'source_device', 'timestamp',
                    'message', 'rule_id', 'rule_name', 'severity'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(messages)
            
            return filename
        except Exception as e:
            print(f"[ArchiveManager] CSV write error: {e}")
            raise
    
    async def _write_jsonl(self, messages: List[dict], timestamp: str) -> str:
        """Write messages to JSONL file"""
        filename = f"messages_{timestamp}.jsonl"
        filepath = os.path.join(self.archive_path, filename)
        
        try:
            with open(filepath, 'w') as f:
                for msg in messages:
                    f.write(json.dumps(msg) + '\n')
            
            return filename
        except Exception as e:
            print(f"[ArchiveManager] JSONL write error: {e}")
            raise
    
    async def _record_archive(self, filename: str, messages: List[dict]):
        """Record archive in database"""
        if not self.database.db or not messages:
            return
        
        try:
            archive_id = str(uuid.uuid4())
            filepath = os.path.join(self.archive_path, filename)
            size_bytes = os.path.getsize(filepath)
            
            earliest_timestamp = messages[0]['timestamp']
            latest_timestamp = messages[-1]['timestamp']
            
            cursor = await self.database.db.cursor()
            await cursor.execute("""
                INSERT INTO archives (
                    id, filename, message_count, size_bytes,
                    earliest_message_timestamp, latest_message_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                archive_id,
                filename,
                len(messages),
                size_bytes,
                earliest_timestamp,
                latest_timestamp
            ))
            
            await self.database.db.commit()
        except Exception as e:
            print(f"[ArchiveManager] Error recording archive: {e}")
    
    async def _delete_archived_messages(self, cutoff_date: datetime):
        """Delete archived messages from database"""
        if not self.database.db:
            return
        
        try:
            cursor = await self.database.db.cursor()
            await cursor.execute(
                "DELETE FROM messages WHERE timestamp < ?",
                (cutoff_date.isoformat(),)
            )
            
            # Also clean up related records
            await cursor.execute("""
                DELETE FROM snmp_messages 
                WHERE message_id NOT IN (SELECT id FROM messages)
            """)
            
            await cursor.execute("""
                DELETE FROM syslog_messages 
                WHERE message_id NOT IN (SELECT id FROM messages)
            """)
            
            await self.database.db.commit()
            
            # Vacuum to reclaim space
            await self.database.db.execute("VACUUM")
            print("[ArchiveManager] Database vacuumed")
            
        except Exception as e:
            print(f"[ArchiveManager] Error deleting archived messages: {e}")
```
```

### 7.3 File Buffer

**File**: `mutt/storage/buffer.py`

```python
import json
import os
from pathlib import Path
from typing import List

from mutt.models.message import Message

class FileBuffer:
    """File-based buffer for message overflow"""
    
    def __init__(self, config: dict):
        self.config = config
        self.buffer_path = config['storage']['file_buffer']['path']
        self.max_size_mb = config['storage']['file_buffer'].get('max_size_mb', 500)
        self.enabled = config['storage']['file_buffer'].get('enabled', True)
        
        # Ensure directory exists
        Path(self.buffer_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def write_messages(self, messages: List[Message]):
        """Append messages to file buffer (JSONL format)"""
        if not self.enabled:
            return
        
        try:
            with open(self.buffer_path, 'a') as f:
                for msg in messages:
                    # Convert message to dict
                    msg_dict = {
                        'id': msg.id,
                        'type': msg.type.value,
                        'source_ip': msg.source_ip,
                        'source_device': msg.source_device,
                        'timestamp': msg.timestamp.isoformat(),
                        'raw_message': msg.raw_message,
                        'matched_rule_id': msg.matched_rule_id,
                        'matched_rule_name': msg.matched_rule_name
                    }
                    f.write(json.dumps(msg_dict) + '\n')
            
            # Check if buffer exceeded max size
            await self._check_size_limit()
            
        except Exception as e:
            print(f"[FileBuffer] Write error: {e}")
            raise
    
    async def _check_size_limit(self):
        """Clear buffer if it exceeds max size"""
        try:
            if os.path.exists(self.buffer_path):
                size_mb = os.path.getsize(self.buffer_path) / (1024 * 1024)
                if size_mb > self.max_size_mb:
                    print(f"[FileBuffer] Buffer exceeded {self.max_size_mb}MB, clearing...")
                    os.remove(self.buffer_path)
        except Exception as e:
            print(f"[FileBuffer] Size check error: {e}")
```

### 7.6 Auth Failure Tracker

**File**: `mutt/storage/auth_failure_tracker.py`

```python
import uuid
from datetime import datetime
from typing import List, Optional

from mutt.storage.database import Database

class AuthFailureTracker:
    """Tracks SNMPv3 authentication failures"""
    
    def __init__(self, database: Database):
        self.database = database
    
    async def record_failure(self, username: str, hostname: str):
        """Record an auth failure for a username"""
        if not self.database.db:
            return
        
        try:
            cursor = await self.database.db.cursor()
            
            # Check if record exists
            await cursor.execute(
                "SELECT id FROM snmpv3_auth_failures WHERE username = ?",
                (username,)
            )
            existing = await cursor.fetchone()
            
            if existing:
                # Update existing record
                await cursor.execute("""
                    UPDATE snmpv3_auth_failures
                    SET num_failures = num_failures + 1,
                        last_failure = CURRENT_TIMESTAMP,
                        hostname = ?
                    WHERE username = ?
                """, (hostname, username))
            else:
                # Create new record
                failure_id = str(uuid.uuid4())
                await cursor.execute("""
                    INSERT INTO snmpv3_auth_failures (
                        id, username, hostname, num_failures, last_failure
                    ) VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (failure_id, username, hostname))
            
            await self.database.db.commit()
            print(f"[AuthFailureTracker] Recorded failure for {username} from {hostname}")
            
        except Exception as e:
            print(f"[AuthFailureTracker] Error recording failure: {e}")
    
    async def clear_failure(self, username: str):
        """Clear auth failure for a username (successful decryption)"""
        if not self.database.db:
            return
        
        try:
            cursor = await self.database.db.cursor()
            await cursor.execute(
                "DELETE FROM snmpv3_auth_failures WHERE username = ?",
                (username,)
            )
            await self.database.db.commit()
            print(f"[AuthFailureTracker] Cleared failures for {username}")
        except Exception as e:
            print(f"[AuthFailureTracker] Error clearing failure: {e}")
    
    async def get_all_failures(self) -> List[dict]:
        """Get all current auth failures"""
        if not self.database.db:
            return []
        
        try:
            cursor = await self.database.db.cursor()
            await cursor.execute("""
                SELECT username, hostname, num_failures, last_failure
                FROM snmpv3_auth_failures
                ORDER BY num_failures DESC, last_failure DESC
            """)
            
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'username': row[0],
                    'hostname': row[1],
                    'num_failures': row[2],
                    'last_failure': row[3]
                })
            
            return results
        except Exception as e:
            print(f"[AuthFailureTracker] Error fetching failures: {e}")
            return []
```

---

## 8. Main Daemon

**File**: `mutt/daemon.py`

```python
import asyncio
import signal
import yaml
from pathlib import Path

from mutt.listeners.snmp_listener import SNMPListener
from mutt.listeners.syslog_listener import SyslogListener
from mutt.processors.message_processor import MessageProcessor
from mutt.logger import setup_logging

class MUTTDaemon:
    """Main MUTT daemon orchestrator"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        setup_logging(self.config)
        
        self.processor = MessageProcessor(self.config)
        self.listeners = []
        self.running = False
    
    def _load_config(self) -> dict:
        """Load YAML configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"[MUTTDaemon] Config load error: {e}")
            raise
    
    async def start(self):
        """Start MUTT daemon"""
        self.running = True
        print("[MUTTDaemon] Starting...")
        
        # Create listeners based on config
        if self.config['listeners'].get('snmp', {}).get('enabled'):
            snmp_listener = SNMPListener(self.processor.queue, self.config)
            self.listeners.append(snmp_listener)
            print("[MUTTDaemon] SNMP listener created")
        
        if self.config['listeners'].get('syslog', {}).get('enabled'):
            syslog_listener = SyslogListener(self.processor.queue, self.config)
            self.listeners.append(syslog_listener)
            print("[MUTTDaemon] Syslog listener created")
        
        # Start all components
        tasks = [
            self.processor.start(),
        ]
        
        for listener in self.listeners:
            tasks.append(listener.start())
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._signal_handler)
        
        print("[MUTTDaemon] Running...")
        await asyncio.gather(*tasks)
    
    def _signal_handler(self):
        """Handle shutdown signals"""
        print("[MUTTDaemon] Shutdown signal received")
        self.running = False
        for listener in self.listeners:
            listener.running = False
        self.processor.running = False

async def main():
    """Entry point"""
    config_path = './config/mutt_config.yaml'
    daemon = MUTTDaemon(config_path)
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        print("[MUTTDaemon] Interrupted")
    finally:
        await daemon.processor.stop()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## 9. Requirements & Dependencies

**File**: `requirements.txt`

```
# Core async/networking
pysnmp==5.0.0
aiosqlite==0.19.0

# Configuration
PyYAML==6.0.1

# Logging
colorama==0.4.6

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1

# Development
black==23.12.0
flake8==6.1.0
```

---

## 10. Build Instructions

### 10.1 Initial Setup

```bash
# Create project directory
mkdir mutt_home && cd mutt_home

# Create Python virtual environment
python3.9 -m venv venv
source venv/bin/activate

# Create directory structure
mkdir -p mutt/{listeners,processors,storage,models,utils}
mkdir -p config logs data tests

# Install dependencies
pip install -r requirements.txt
```

### 10.2 File Creation Order

1. **Models** (dataclasses first, no dependencies)
   - `mutt/models/message.py`
   - `mutt/models/rules.py`
   - `mutt/models/credentials.py`

2. **Configuration**
   - `mutt/config.py` (config loader)
   - `config/mutt_config.yaml`
   - `config/alert_rules.yaml`

3. **Storage Layer**
   - `mutt/storage/schema.py`
   - `mutt/storage/database.py`
   - `mutt/storage/device_registry.py`
   - `mutt/storage/archive_manager.py`
   - `mutt/storage/buffer.py`

4. **Listeners**
   - `mutt/listeners/base.py`
   - `mutt/listeners/snmp_listener.py`
   - `mutt/listeners/syslog_listener.py`

5. **Processors**
   - `mutt/processors/validator.py`
   - `mutt/processors/pattern_matcher.py`
   - `mutt/processors/enricher.py`
   - `mutt/processors/message_router.py`
   - `mutt/processors/message_processor.py`

6. **Utilities & Logging**
   - `mutt/logger.py`
   - `mutt/utils/helpers.py`

7. **Main Daemon**
   - `mutt/daemon.py`
   - `mutt/__init__.py`

8. **Tests**
   - `tests/test_models.py`
   - `tests/test_listeners.py`
   - `tests/test_processor.py`
   - `tests/test_database.py`

---

## 11. Data Flow Summary

```
1. NETWORK DEVICES send SNMP/Syslog
   ↓
2. SNMPListener / SyslogListener receive and parse
   ↓
3. Messages enqueued to asyncio.Queue
   ↓
4. MessageProcessor dequeues (150 msgs/sec capacity)
   ↓
5. Validator: Check required fields
   ↓
6. PatternMatcher: Match against alert rules
   ↓
7. Enricher: Add metadata (DNS, etc.)
   ↓
8. MessageRouter: Route based on rule action (STORE/WEBHOOK/DISCARD)
   ├─→ STORE: Add to batch
   ├─→ WEBHOOK: Send to external service (future)
   └─→ DISCARD: Drop message
   ↓
9. For STORE actions: Accumulate in batch (100 messages max or 5 sec timeout)
   ↓
10. Batch write to SQLite via aiosqlite
    ↓
11. If DB write fails: Fallback to file buffer (overflow.jsonl)
    ↓
12. Web UI (separate codebase) reads from SQLite
```

---

## 12. Future Extensibility

The design supports these future features without major refactoring:

- **Webhook Output**: Add `WebhookAction` class in processors
- **Vault Integration**: Replace CSV credential loading with Vault client
- **Clustering**: Add message ID tracking across instances
- **Hot Rule Reload**: Implement async watcher for rules file changes
- **Metrics/Observability**: Add Prometheus metrics to components
- **Multi-database Support**: Abstract Database class to support PostgreSQL/MySQL

---

## 13. Testing Strategy

**Unit Tests** (`tests/test_models.py`):
- Message dataclass creation and validation
- Rule matching logic

**Integration Tests** (`tests/test_listeners.py`):
- Mock network data → Listener → Queue
- Verify message enqueuing

**Processor Tests** (`tests/test_processor.py`):
- Validate → Match → Enrich pipeline
- Batch accumulation and flush logic

**Database Tests** (`tests/test_database.py`):
- Schema creation
- Write/read operations with aiosqlite
- File buffer fallback

---

## 14. Deployment Checklist

- [ ] All modules implemented from build instructions
- [ ] Configuration files created and customized
- [ ] Tests passing (pytest)
- [ ] Listeners can bind to ports (permissions check)
- [ ] Database initialization successful
- [ ] File buffer directory writable
- [ ] Daemon starts without errors
- [ ] Messages flowing end-to-end to database

---

**End of Design Document**

*This document provides the complete blueprint for MUTT implementation. Hand this to Copilot with clear instructions that this is the architectural specification to follow.*
