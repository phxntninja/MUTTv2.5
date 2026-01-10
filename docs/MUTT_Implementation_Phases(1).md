# MUTT Implementation - Phase-by-Phase Guide for DeepSeek

This document breaks down the MUTT architecture into 5 manageable phases for code generation. Each phase is ~200-400 lines and can be built/tested independently.

---

## Phase 1: Models & Configuration (~300 lines)

**Objective**: Build the foundational data structures and configuration system, including SNMPv3 credential support.

**Files to Create**:
1. `mutt/models/message.py` - Message dataclasses
2. `mutt/models/rules.py` - Alert rule dataclasses
3. `mutt/models/credentials.py` - SNMPv3 credential dataclasses
4. `mutt/config.py` - YAML config loader
5. `config/mutt_config.yaml` - Configuration file
6. `config/alert_rules.yaml` - Alert rules file
7. `config/snmpv3_credentials.yaml` - SNMPv3 credentials file

**Dependencies**: None (standard library only)

**Testing**: 
```bash
python -c "from mutt.models.credentials import SNMPv3Credential; print('Phase 1 OK')"
```

**Deliverables**:
- Message dataclasses with all required fields
- SNMPTrap and SyslogMessage subclasses
- AlertRule dataclass with pattern matching support
- SNMPv3Credential and SNMPv3CredentialSet dataclasses
- Credential loader that parses snmpv3_credentials.yaml by username
- YAML config loader that parses mutt_config.yaml
- Sample config files (all three YAML files)

**Notes for DeepSeek**:
- Use `dataclasses` module (standard library)
- Use `yaml` module (install via pip)
- Keep enums for MessageType, Severity, PatternType, ActionType
- SNMPv3Credential should have: username, auth_type, auth_password, priv_type, priv_password, priority, active
- Credential loader should organize by username and sort by priority
- Config loader should return dict-like structure

---

## Phase 2: Storage Layer (~400 lines)

**Objective**: Build database, device registry, and archive manager.

**Files to Create**:
1. `mutt/storage/schema.py` - Database schema SQL
2. `mutt/storage/database.py` - SQLite wrapper (aiosqlite)
3. `mutt/storage/device_registry.py` - Device tracking
4. `mutt/storage/archive_manager.py` - Message archiving
5. `mutt/storage/buffer.py` - File buffer for overflow

**Dependencies**: Phase 1 (models)

**Testing**:
```bash
python -c "from mutt.storage.database import Database; print('Phase 2 OK')"
```

**Deliverables**:
- Complete SQLite schema (messages, devices, archives, snmp_messages, syslog_messages, snmpv3_auth_failures tables)
- Database class with aiosqlite connection, initialize, write_messages, get_messages methods
- DeviceRegistry class with update_device, get_device_snmp_version methods
- ArchiveManager class with check_and_archive, size/time threshold logic
- FileBuffer class for JSONL overflow handling
- AuthFailureTracker class with methods to record/clear auth failures

**Critical**: 
- Database initialization must create all tables on first run
- Device registry should handle updates (INSERT OR UPDATE)
- Archive manager should support both CSV and JSONL formats
- All methods must be async (aiosqlite)

**Notes for DeepSeek**:
- Use `aiosqlite` for async database operations
- Archive manager should archive messages > 1 day old
- Archive filename format: `messages_YYYYMMDD_HHMMSS.csv`
- Devices table is permanent (never archived)
- snmpv3_auth_failures table schema: id (TEXT PRIMARY KEY), username (TEXT UNIQUE), hostname (TEXT, last device that failed), num_failures (INTEGER), last_failure (DATETIME)
- AuthFailureTracker should have methods: record_failure(username, hostname), clear_failure(username), get_all_failures()

---

## Phase 3: Listeners (~400 lines)

**Objective**: Build SNMP and Syslog message receivers with SNMPv3 credential support.

**Files to Create**:
1. `mutt/listeners/base.py` - Abstract listener base class
2. `mutt/listeners/snmp_listener.py` - SNMP trap listener with v3 credential support
3. `mutt/listeners/syslog_listener.py` - Syslog listener

**Dependencies**: Phase 1 (models, credentials), Phase 2 (auth_failure_tracker)

**Testing**:
```bash
python -c "from mutt.listeners.snmp_listener import SNMPListener; print('Phase 3 OK')"
```

**Deliverables**:
- BaseListener abstract class with listen(), parse_message(), enqueue_message() methods
- SNMPListener that receives on port 5162 UDP, parses SNMP traps
- SNMPListener v3 credential lookup by username from loaded credentials
- SNMPListener auth failure tracking (tries credentials in priority order, records failures)
- SyslogListener that receives on port 5514 UDP/TCP, parses RFC 3164 syslog
- Both listeners generate UUID for each message
- Parse into Message/SNMPTrap/SyslogMessage objects

**Critical**:
- Listeners must enqueue to an asyncio.Queue passed in __init__
- Parse raw network data into proper Message objects
- Handle parsing errors gracefully (don't crash on malformed data)
- SNMPListener must try SNMPv3 credentials in priority order (lowest priority number first)
- On successful v3 decryption: clear any auth failures for that username
- On v3 decryption failure: record failure in auth_failure_tracker with username + hostname
- Track message count for logging

**Notes for DeepSeek**:
- Use `pysnmp-lextudio` library for SNMP v1/v2c/v3 support
- Use standard library `socket` for syslog
- Syslog regex for RFC 3164: `<(\d+)>(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s*(.*)`
- SNMPListener receives loaded credentials dict (username -> list of credentials sorted by priority)
- SNMPListener receives auth_failure_tracker instance for recording/clearing failures
- For v3 traps: extract username from trap, look up credentials, try each in priority order
- If all credentials fail, call auth_failure_tracker.record_failure(username, source_hostname)

---

## Phase 4: Processors (~400 lines)

**Objective**: Build the message processing pipeline components.

**Files to Create**:
1. `mutt/processors/validator.py` - Message validation
2. `mutt/processors/pattern_matcher.py` - Pattern matching against rules
3. `mutt/processors/enricher.py` - Message enrichment
4. `mutt/processors/message_router.py` - Route messages to outputs

**Dependencies**: Phase 1 (models), Phase 2 (device_registry)

**Testing**:
```bash
python -c "from mutt.processors.validator import Validator; print('Phase 4 OK')"
```

**Deliverables**:
- Validator class with validate() method checking required fields
- PatternMatcher class that loads rules.yaml and matches messages (regex/keyword/exact)
- Enricher class with reverse DNS lookup and DeviceRegistry update calls
- MessageRouter class with handler registry and route() method

**Critical**:
- PatternMatcher must handle regex, keyword, and exact matching
- Enricher must call device_registry.update_device() with SNMP/syslog version info
- MessageRouter must support handler registration for STORE/WEBHOOK/DISCARD actions
- All methods must be async

**Notes for DeepSeek**:
- Use `re` module for regex matching
- Validator should populate message.validation_errors list
- PatternMatcher should reload rules periodically (config option)
- MessageRouter handlers should be callables (async functions)

---

## Phase 5: Main Processor & Daemon (~300 lines)

**Objective**: Build the main orchestrator and daemon entry point.

**Files to Create**:
1. `mutt/processors/message_processor.py` - Main processor orchestrator
2. `mutt/daemon.py` - Daemon entry point
3. `mutt/logger.py` - Logging setup

**Dependencies**: All previous phases

**Testing**:
```bash
python -c "from mutt.daemon import MUTTDaemon; print('Phase 5 OK')"
```

**Deliverables**:
- MessageProcessor class with:
  - Shared asyncio.Queue for listeners
  - All processor components (validator, matcher, enricher, router, database, archive)
  - Batch accumulation and writing logic
  - Three concurrent tasks: process_loop, batch_write_loop, archive_check_loop
  - Handler registration for STORE/WEBHOOK/DISCARD actions
  
- MUTTDaemon class with:
  - Config loading from YAML
  - Listener instantiation (SNMP + Syslog)
  - Processor start
  - Signal handling (SIGINT, SIGTERM) for graceful shutdown
  
- Logger setup with colorama for colored output

**Critical**:
- MessageProcessor must run 3 concurrent asyncio tasks
- Batch flushing on timeout (5 sec) or batch size (100 msgs)
- STORE handler adds to batch, WEBHOOK handler is placeholder, DISCARD handler does nothing
- Graceful shutdown must flush remaining batch before exit

**Notes for DeepSeek**:
- Use `asyncio.gather()` to run concurrent tasks
- Use `signal` module for shutdown handlers
- Use `colorama` for colored logging
- Main entry point: `async def main()` with `asyncio.run(main())`

---

## Phase 6: Integration & Glue (~100 lines)

**Objective**: Wire everything together and create startup files.

**Files to Create**:
1. `mutt/__init__.py` - Package initialization
2. `requirements.txt` - Python dependencies
3. `run.sh` - Startup script
4. Integration test (optional)

**This phase happens AFTER all 5 phases are complete and tested.**

---

## Implementation Instructions for DeepSeek

### Per-Phase Workflow

For each phase, provide DeepSeek with:

1. **The Phase Section** from this document (explains what to build)
2. **Relevant sections** from MUTT_Design_Complete.md (code examples, class signatures)
3. **Clear prompt**:

```
Build Phase [N]: [Phase Name]

Files to create:
- [file 1]
- [file 2]

Requirements:
- [req 1]
- [req 2]

Reference the following sections from MUTT_Design_Complete.md:
- Section [X]: [Component Name]

Create complete, working code. Don't skip implementations.
Test imports work: python -c "from mutt.X import Y; print('OK')"
```

### After Each Phase

1. **Test imports** work without errors
2. **Review code** quality and consistency
3. **Fix issues** before moving to next phase
4. **Commit to git** (if using version control)

### After All 5 Phases

Provide Phase 6 prompt:

```
Wire together Phases 1-5. Create:

1. mutt/__init__.py - Import all modules
2. requirements.txt - All pip dependencies
3. run.sh - Startup script that runs: python -m mutt.daemon
4. Integration test - Verify all imports work

Reference: MUTT_Design_Complete.md Section 14 (Deployment Checklist)

Ensure:
- No circular imports
- All async functions properly defined
- Config files exist in config/ directory
- Project structure matches design
```

---

## File Structure (Reference)

```
mutt_home/
├── mutt/
│   ├── __init__.py                      [Phase 6]
│   ├── daemon.py                        [Phase 5]
│   ├── logger.py                        [Phase 5]
│   ├── listeners/
│   │   ├── __init__.py
│   │   ├── base.py                      [Phase 3]
│   │   ├── snmp_listener.py             [Phase 3]
│   │   └── syslog_listener.py           [Phase 3]
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── validator.py                 [Phase 4]
│   │   ├── pattern_matcher.py           [Phase 4]
│   │   ├── enricher.py                  [Phase 4]
│   │   ├── message_router.py            [Phase 4]
│   │   └── message_processor.py         [Phase 5]
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── schema.py                    [Phase 2]
│   │   ├── database.py                  [Phase 2]
│   │   ├── device_registry.py           [Phase 2]
│   │   ├── archive_manager.py           [Phase 2]
│   │   └── buffer.py                    [Phase 2]
│   ├── models/
│   │   ├── __init__.py
│   │   ├── message.py                   [Phase 1]
│   │   ├── rules.py                     [Phase 1]
│   │   └── credentials.py               [Phase 1 - SNMPv3 credentials]
│   └── utils/
│       ├── __init__.py
│       └── helpers.py                   [Phase 6 - stub]
├── config/
│   ├── mutt_config.yaml                 [Phase 1]
│   ├── alert_rules.yaml                 [Phase 1]
│   └── snmpv3_credentials.yaml          [Phase 1]
├── data/
│   ├── archives/                        [created at runtime]
│   └── messages.db                      [created at runtime]
├── logs/
│   └── mutt.log                         [created at runtime]
├── tests/
│   ├── __init__.py
│   ├── test_models.py                   [Phase 1 - optional]
│   ├── test_storage.py                  [Phase 2 - optional]
│   ├── test_listeners.py                [Phase 3 - optional]
│   ├── test_processors.py               [Phase 4 - optional]
│   └── test_integration.py              [Phase 6 - optional]
├── requirements.txt                     [Phase 6]
├── run.sh                               [Phase 6]
├── README.md
└── .gitignore
```

---

## Dependencies by Phase

**Phase 1**: 
- Standard library: dataclasses, enum, typing
- External: PyYAML

**Phase 2**:
- Phase 1
- External: aiosqlite
- Standard library: asyncio, json, datetime, uuid, csv, pathlib

**Phase 3**:
- Phase 1 (models, credentials)
- Phase 2 (auth_failure_tracker)
- External: pysnmp-lextudio
- Standard library: asyncio, uuid, datetime, re, socket

**Phase 4**:
- Phase 1, Phase 2
- External: PyYAML
- Standard library: asyncio, re, socket, typing

**Phase 5**:
- Phase 1, Phase 2, Phase 3, Phase 4
- External: colorama
- Standard library: asyncio, signal, yaml

**Phase 6**:
- All phases
- External: all of the above

---

## Quick Checklist

### Before Each Phase
- [ ] Read phase description
- [ ] Get relevant sections from MUTT_Design_Complete.md
- [ ] Prepare prompt for DeepSeek

### During Each Phase
- [ ] DeepSeek generates code
- [ ] Review for completeness
- [ ] Check syntax/imports

### After Each Phase
- [ ] Test imports work
- [ ] No circular dependencies
- [ ] Commit code
- [ ] Move to next phase

### After All Phases
- [ ] Create glue files (Phase 6)
- [ ] Run full integration test
- [ ] Deploy

---

**End of Phase Guide**

When ready to start Phase 1 with DeepSeek, use the prompt template from the "Implementation Instructions" section above.
