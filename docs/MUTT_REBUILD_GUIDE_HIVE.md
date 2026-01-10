# MUTT Rebuild Guide - Hive Implementation
## Complete rebuild of MUTT with SNMPv3 credential support

**Date:** January 2026  
**Status:** Ready for implementation  
**Tool:** ai-hive with phase-by-phase approach

---

## Overview

This guide will rebuild MUTT 2.5 from scratch using the Hive implementation tool. The rebuild incorporates SNMPv3 credential handling with auth failure tracking.

**Key Addition:** SNMPv3 credentials are now managed by username with priority-based rotation support, plus auth failure tracking.

---

## Prerequisites

- Python 3.9.6+
- Virtual environment created and activated
- Basic YAML knowledge
- ai-hive tool available

---

## Phase 1: Models & Configuration

### Objective
Build foundational data structures including SNMPv3 credential models.

### Files to Create
1. `mutt/models/message.py` - Message dataclasses
2. `mutt/models/rules.py` - Alert rule dataclasses  
3. `mutt/models/credentials.py` - SNMPv3 credential dataclasses (**NEW**)
4. `mutt/config.py` - Config + credential loaders
5. `config/mutt_config.yaml` - Main config
6. `config/alert_rules.yaml` - Alert rules
7. `config/snmpv3_credentials.yaml` - SNMPv3 credentials (**NEW**)

### Prompt for Engineer Agent

```
Build Phase 1: Models & Configuration

Create these files with complete, working code:
1. mutt/models/message.py
   - Message dataclass with: id, type, source_ip, source_device, timestamp, raw_message
   - SNMPTrap subclass with: oid, trap_type, snmp_version
   - SyslogMessage subclass with: facility, level, program, process_id, tag
   - Enums: MessageType, Severity, PatternType, ActionType

2. mutt/models/rules.py
   - AlertRule dataclass with: id, name, pattern_type, pattern, keywords, severity, action, enabled

3. mutt/models/credentials.py (**NEW**)
   - SNMPv3Credential dataclass with: priority, auth_type, auth_password, priv_type, priv_password, active
   - SNMPv3CredentialSet dataclass with: username, credentials (list), get_active_credentials() method

4. mutt/config.py
   - ConfigLoader.load_config(path) - loads YAML config
   - CredentialLoader.load_credentials(path) - loads SNMPv3 credentials by username, returns Dict[username -> SNMPv3CredentialSet]
   - Both should handle errors gracefully with logging

5. config/mutt_config.yaml
   - daemon section: log_level, log_file, pid_file
   - listeners section: snmp (port 5162) and syslog (port 5514)
   - processor section: queue_max_size, batch settings
   - storage section: database path, file buffer settings, archiver config
   - pattern_matching section: rules_file path

6. config/alert_rules.yaml
   - Example rules with regex, keyword, and exact matching

7. config/snmpv3_credentials.yaml (**NEW**)
   - Example showing multiple usernames
   - Multiple credential sets per username with priority (for rotation)
   - active/inactive flags for safe credential transitions

Reference sections from MUTT_Design_Complete.md:
- Section 5: Data Models
- Section 5A: Credential Loader
- Section 4: Configuration

Test:
python -c "from mutt.models.credentials import SNMPv3CredentialSet; from mutt.config import CredentialLoader; print('Phase 1 OK')"
```

### Verification Checklist
- [ ] All imports work without errors
- [ ] No circular dependencies
- [ ] Dataclasses are properly defined
- [ ] Config files are valid YAML
- [ ] CredentialLoader returns correct structure

---

## Phase 2: Storage Layer

### Objective
Build database, device registry, archive manager, and auth failure tracker.

### Files to Create
1. `mutt/storage/schema.py` - Database schema SQL
2. `mutt/storage/database.py` - SQLite async wrapper
3. `mutt/storage/device_registry.py` - Device tracking
4. `mutt/storage/archive_manager.py` - Message archiving
5. `mutt/storage/buffer.py` - File buffer for overflow
6. `mutt/storage/auth_failure_tracker.py` - SNMPv3 auth failure tracking (**NEW**)

### Prompt for Engineer Agent

```
Build Phase 2: Storage Layer

Create these files with complete, working code:

1. mutt/storage/schema.py
   - Define SQL_SCHEMA constant with CREATE TABLE statements for:
     * messages table (id, type, source_ip, source_device, timestamp, raw_message, validation fields, match fields, etc.)
     * devices table (hostname, source_ip, last_seen_snmp_version, last_seen_syslog, first_seen, last_updated)
     * archives table (filename, message_count, size_bytes, date range)
     * snmp_messages table (message_id, oid, trap_type, snmp_version)
     * syslog_messages table (message_id, facility, level, program, process_id, tag)
     * snmpv3_auth_failures table (**NEW**) - (username UNIQUE, hostname, num_failures, last_failure)
   - Include all necessary indexes

2. mutt/storage/database.py
   - Database class using aiosqlite
   - Methods: initialize(), write_messages(batch), get_messages(limit, offset), close()
   - All async methods

3. mutt/storage/device_registry.py
   - DeviceRegistry class
   - Methods: update_device(hostname, source_ip, snmp_version, syslog_seen), get_device_snmp_version(hostname), get_all_devices()
   - All async

4. mutt/storage/archive_manager.py
   - ArchiveManager class with size + time threshold checking
   - Methods: check_and_archive(), exports to CSV files
   - Auto-cleanup and VACUUM

5. mutt/storage/buffer.py
   - FileBuffer class for overflow
   - write_messages(list) method
   - Auto-clear when size exceeded

6. mutt/storage/auth_failure_tracker.py (**NEW**)
   - AuthFailureTracker class
   - Methods: record_failure(username, hostname), clear_failure(username), get_all_failures()
   - All async
   - Used for tracking SNMPv3 auth failures

Reference sections from MUTT_Design_Complete.md:
- Section 6.3: Database Wrapper
- Section 6.4: Device Registry
- Section 6.5: Archive Manager
- Section 7.3: File Buffer
- Section 7.6: Auth Failure Tracker (**NEW**)

Test:
python -c "from mutt.storage.database import Database; from mutt.storage.auth_failure_tracker import AuthFailureTracker; print('Phase 2 OK')"
```

### Verification Checklist
- [ ] Database initializes without errors
- [ ] Tables created with correct schema
- [ ] All storage methods are async
- [ ] Auth failure tracker queries work
- [ ] No import errors

---

## Phase 3: Listeners

### Objective
Build SNMP and Syslog listeners with SNMPv3 credential support.

### Files to Create
1. `mutt/listeners/base.py` - Abstract base class
2. `mutt/listeners/snmp_listener.py` - SNMP with v3 credentials
3. `mutt/listeners/syslog_listener.py` - RFC 3164 syslog

### Prompt for Engineer Agent

```
Build Phase 3: Network Listeners

Create these files with complete, working code:

1. mutt/listeners/base.py
   - BaseListener abstract class
   - Methods: listen() (abstract), parse_message() (abstract), enqueue_message()
   - Attributes: queue, config, running, message_count

2. mutt/listeners/snmp_listener.py (**UPDATED**)
   - SNMPListener class extends BaseListener
   - Constructor receives: queue, config, credentials_dict (Dict[username -> SNMPv3CredentialSet]), auth_failure_tracker
   - listen() receives SNMP traps on port 5162 UDP
   - parse_message() handles:
     * SNMPv1 traps
     * SNMPv2c traps (with community string)
     * SNMPv3 traps WITH CREDENTIAL LOOKUP:
       - Extract username from v3 trap
       - Look up username in credentials_dict
       - Try each credential in priority order (via get_active_credentials())
       - If decryption succeeds: call auth_failure_tracker.clear_failure(username)
       - If all fail: call auth_failure_tracker.record_failure(username, source_hostname)
       - Log failure clearly
   - Returns SNMPTrap object with snmp_version field set

3. mutt/listeners/syslog_listener.py
   - SyslogListener class extends BaseListener
   - listen() receives syslog on port 5514 UDP/TCP
   - parse_message() uses RFC 3164 regex to parse
   - Returns SyslogMessage object

Reference sections from MUTT_Design_Complete.md:
- Section 6.1: SNMP Listener (**UPDATED** - see credential lookup logic)
- Section 6.2: Syslog Listener

Test:
python -c "from mutt.listeners.snmp_listener import SNMPListener; from mutt.listeners.syslog_listener import SyslogListener; print('Phase 3 OK')"
```

### Verification Checklist
- [ ] Listeners bind to correct ports
- [ ] Message parsing works
- [ ] SNMPv3 credential lookup works
- [ ] Auth failures are tracked correctly
- [ ] No import errors

---

## Phase 4: Processors

### Objective
Build message validation, pattern matching, enrichment, and routing.

### Files to Create
1. `mutt/processors/validator.py` - Message validation
2. `mutt/processors/pattern_matcher.py` - Pattern matching against rules
3. `mutt/processors/enricher.py` - Message enrichment with device tracking
4. `mutt/processors/message_router.py` - Route to outputs based on rules

### Prompt for Engineer Agent

```
Build Phase 4: Message Processors

Create these files with complete, working code:

1. mutt/processors/validator.py
   - Validator class
   - validate(message) method checks required fields
   - Sets message.validated = True/False
   - Populates message.validation_errors list

2. mutt/processors/pattern_matcher.py
   - PatternMatcher class
   - Loads alert_rules.yaml
   - match(message) tries all rules in order
   - Supports: regex, keyword, exact matching
   - Sets message.matched_rule_id, matched_rule_name, match_severity if matched
   - Returns True/False

3. mutt/processors/enricher.py
   - Enricher class receives device_registry in constructor
   - enrich(message) performs:
     * Reverse DNS lookup on source_ip
     * Calls device_registry.update_device() to track SNMP/syslog versions
     * Adds to message.enriched_data dict

4. mutt/processors/message_router.py
   - MessageRouter class
   - register_handler(action_type, handler_func) - registers handlers
   - route(message) - routes based on matched rule action
   - Supports: STORE, WEBHOOK (placeholder), DISCARD actions
   - Fallback: if handler fails, try STORE as backup

Reference sections from MUTT_Design_Complete.md:
- Section 6.6: Validator
- Section 6.7: Pattern Matcher
- Section 6.8: Enricher
- Section 6.9: Message Router

Test:
python -c "from mutt.processors.validator import Validator; from mutt.processors.message_router import MessageRouter; print('Phase 4 OK')"
```

### Verification Checklist
- [ ] Validation works correctly
- [ ] Pattern matching handles all types
- [ ] Enrichment calls device registry
- [ ] Router registers and calls handlers
- [ ] No import errors

---

## Phase 5: Main Processor & Daemon

### Objective
Build the orchestrator and daemon entry point.

### Files to Create
1. `mutt/processors/message_processor.py` - Main orchestrator
2. `mutt/daemon.py` - Daemon entry point
3. `mutt/logger.py` - Logging setup

### Prompt for Engineer Agent

```
Build Phase 5: Main Processor & Daemon

Create these files with complete, working code:

1. mutt/processors/message_processor.py
   - MessageProcessor class
   - Constructor initializes all components: database, device_registry, archive_manager, auth_failure_tracker, validator, pattern_matcher, enricher, router
   - start() method runs 3 concurrent asyncio tasks:
     * _process_loop() - dequeue, validate, match, enrich, route
     * _batch_write_loop() - flush batches to database
     * _archive_check_loop() - check archive thresholds every 5 minutes
   - Batch accumulation: 100 messages or 5-second timeout
   - Graceful shutdown with stop() method

2. mutt/daemon.py
   - MUTTDaemon class
   - Loads config from mutt_config.yaml
   - Loads SNMPv3 credentials from snmpv3_credentials.yaml (**NEW**)
   - Creates SNMPListener and SyslogListener with credentials_dict and auth_failure_tracker
   - Starts MessageProcessor
   - Handles SIGINT/SIGTERM signals
   - main() entry point with asyncio.run()

3. mutt/logger.py
   - setup_logging(config) - configure colorama for colored console output
   - Log to file + console

Reference sections from MUTT_Design_Complete.md:
- Section 6.10: Message Processor (UPDATED with auth_failure_tracker)
- Section 8: Main Daemon (UPDATED with credential loading)

Test:
python -c "from mutt.daemon import MUTTDaemon; print('Phase 5 OK')"
```

### Verification Checklist
- [ ] Daemon starts without errors
- [ ] Config loads correctly
- [ ] Credentials load correctly
- [ ] All three concurrent tasks run
- [ ] Graceful shutdown works
- [ ] No import errors

---

## Phase 6: Integration & Glue

### Objective
Wire everything together.

### Files to Create
1. `mutt/__init__.py` - Package initialization
2. `requirements.txt` - Dependencies
3. `run.sh` - Startup script
4. Integration test (optional)

### Prompt for Engineer Agent

```
Build Phase 6: Integration & Glue

Create these files:

1. mutt/__init__.py
   - Import all major classes from submodules
   - Make them available at package level

2. requirements.txt
   - aiosqlite
   - PyYAML
   - pysnmp-lextudio (for SNMP v1/v2c/v3 support)
   - colorama
   - pytest-asyncio (optional, for testing)

3. run.sh
   - #!/bin/bash
   - Activate venv if needed
   - Run: python -m mutt.daemon

4. Verify no circular imports:
   - Create simple test that imports all modules
   - Check that everything loads

Reference: MUTT_Design_Complete.md Section 14 (Deployment Checklist)

Test:
python -c "from mutt import *; print('Phase 6 OK')"
bash run.sh (should start daemon)
```

### Verification Checklist
- [ ] All modules import correctly
- [ ] No circular dependencies
- [ ] requirements.txt has all deps
- [ ] run.sh is executable
- [ ] Daemon starts successfully
- [ ] Test: Send syslog/SNMP trap, verify in database

---

## Testing SNMPv3 Credential Handling

After Phase 5 is complete, test the SNMPv3 flow:

```bash
# 1. Start daemon
python -m mutt.daemon &

# 2. Send test syslog (v2c equivalent)
echo "<14>Jan 10 12:00:00 testhost snmp: trap received" | nc -u -w0 127.0.0.1 5514

# 3. Check database
sqlite3 data/messages.db "SELECT * FROM messages WHERE type='SYSLOG' LIMIT 1;"

# 4. Check devices tracked
sqlite3 data/messages.db "SELECT * FROM devices;"

# 5. If SNMPv3 fails, check auth failures
sqlite3 data/messages.db "SELECT * FROM snmpv3_auth_failures;"
```

---

## Quick Reference: New in This Build

**SNMPv3 Features:**
- Credentials loaded from YAML by username
- Priority-based credential rotation (priority 1 tried first)
- Active/inactive flags for safe credential transitions
- Auth failure tracking (username, hostname, num_failures, timestamp)
- Failed auth doesn't crash system - logged for debugging

**Key Files:**
- `config/snmpv3_credentials.yaml` - Credential definitions
- `mutt/models/credentials.py` - Credential dataclasses
- `mutt/storage/auth_failure_tracker.py` - Failure tracking
- `mutt/listeners/snmp_listener.py` - Updated with v3 support

---

## Hive Implementation Notes

When using ai-hive:
1. Feed each phase sequentially to Engineer agent
2. Review generated code before moving to next phase
3. Test imports at each phase boundary
4. If issues arise, describe the problem clearly and ask for fixes
5. Save working code before moving forward

**Pro tip:** Keep Phase sections focused. If Engineer struggles, break into smaller prompts and combine later.

---

**End of Rebuild Guide**

Use this with ai-hive to completely rebuild MUTT with SNMPv3 support.
