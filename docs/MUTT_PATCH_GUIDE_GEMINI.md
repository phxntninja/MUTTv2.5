# MUTT Patch Guide - Gemini Integration
## Instructions for patching existing MUTT code with SNMPv3 credential support

**Date:** January 2026  
**Status:** Ready for implementation  
**Tool:** Gemini (Claude)  
**Scope:** Add SNMPv3 credentials to existing MUTT 2.5 codebase

---

## Overview

This guide provides specific instructions for Gemini to patch the existing MUTT 2.5 codebase with SNMPv3 credential handling. The existing core is stable; we're adding credentials + auth failure tracking.

**What's being added:**
1. SNMPv3 credential models and loader
2. Auth failure tracking table and tracker class
3. SNMPListener updates to handle v3 credential lookup
4. Daemon updates to load and pass credentials to listeners

---

## Prerequisites

- Existing MUTT 2.5 codebase (6 phases completed)
- All tests passing
- Database can be reset if needed

---

## Patch 1: Add Credential Models

**File:** `mutt/models/credentials.py` (NEW)

**Prompt for Gemini:**

```
Create a new file mutt/models/credentials.py with these dataclasses:

1. SNMPv3Credential dataclass:
   - priority: int (lower = higher priority for rotation)
   - auth_type: str (SHA, MD5, etc.)
   - auth_password: str
   - priv_type: str (AES, DES, etc.)
   - priv_password: str
   - active: bool = True

2. SNMPv3CredentialSet dataclass:
   - username: str
   - credentials: List[SNMPv3Credential]
   - get_active_credentials() method that returns active creds sorted by priority

Include docstrings and type hints. This file should be importable and work with YAML parsing.
```

**Verification:**
```bash
python -c "from mutt.models.credentials import SNMPv3Credential, SNMPv3CredentialSet; print('OK')"
```

---

## Patch 2: Add Credential Loader to Config

**File:** `mutt/config.py` (UPDATE)

**Prompt for Gemini:**

```
Update mutt/config.py to add a CredentialLoader class:

1. Add import: from mutt.models.credentials import SNMPv3CredentialSet, SNMPv3Credential

2. Add CredentialLoader class with:
   - Static method: load_credentials(credentials_path: str) -> Dict[str, SNMPv3CredentialSet]
   - Returns dict keyed by username
   - Each username maps to SNMPv3CredentialSet
   - Credentials should be sorted by priority internally
   - Handle missing file gracefully (return empty dict with warning)
   - Logs: "Loaded credentials for user: {username}"

The method should parse YAML like:
snmpv3_credentials:
  - username: snmpuser
    credentials:
      - priority: 1
        auth_type: SHA
        auth_password: authpass123
        priv_type: AES
        priv_password: privpass456
        active: true
```

**Verification:**
```bash
python -c "from mutt.config import CredentialLoader; print('OK')"
```

---

## Patch 3: Create snmpv3_credentials.yaml

**File:** `config/snmpv3_credentials.yaml` (NEW)

**Prompt for Gemini:**

```
Create config/snmpv3_credentials.yaml with this structure:

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

This shows credential rotation: priority 1 is active (current), priority 2 is inactive (new creds to activate later).
```

---

## Patch 4: Add Auth Failure Tracking Table

**File:** `mutt/storage/schema.py` (UPDATE)

**Prompt for Gemini:**

```
Update mutt/storage/schema.py to add the snmpv3_auth_failures table:

Add this CREATE TABLE statement to SCHEMA before the closing """:

CREATE TABLE IF NOT EXISTS snmpv3_auth_failures (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    hostname TEXT,
    num_failures INTEGER DEFAULT 1,
    last_failure DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_snmpv3_failures_username ON snmpv3_auth_failures(username);

This tracks failed SNMPv3 authentication attempts by username.
```

---

## Patch 5: Add AuthFailureTracker Class

**File:** `mutt/storage/auth_failure_tracker.py` (NEW)

**Prompt for Gemini:**

```
Create mutt/storage/auth_failure_tracker.py with AuthFailureTracker class:

Class needs:
1. Constructor: __init__(self, database: Database)
   - Store database reference

2. Async method: record_failure(username: str, hostname: str)
   - If username exists in snmpv3_auth_failures: increment num_failures, update last_failure, update hostname
   - If doesn't exist: insert new row with num_failures=1
   - Log: "[AuthFailureTracker] Recorded failure for {username} from {hostname}"
   - Handle errors gracefully

3. Async method: clear_failure(username: str)
   - DELETE from snmpv3_auth_failures WHERE username = ?
   - Log: "[AuthFailureTracker] Cleared failures for {username}"
   - Handle errors

4. Async method: get_all_failures() -> List[dict]
   - SELECT from snmpv3_auth_failures ORDER BY num_failures DESC, last_failure DESC
   - Return list of dicts with keys: username, hostname, num_failures, last_failure
   - Return empty list on error

All methods must be async (use await for db operations).
```

**Verification:**
```bash
python -c "from mutt.storage.auth_failure_tracker import AuthFailureTracker; print('OK')"
```

---

## Patch 6: Update SNMPListener for v3 Credentials

**File:** `mutt/listeners/snmp_listener.py` (UPDATE)

**Prompt for Gemini:**

```
Update mutt/listeners/snmp_listener.py SNMPListener class:

1. Update constructor to accept two new parameters:
   - credentials_dict: Dict[str, SNMPv3CredentialSet] (from CredentialLoader)
   - auth_failure_tracker: AuthFailureTracker instance
   
   Store both as instance variables.

2. Update parse_message() to handle SNMPv3 credential lookup:
   
   For SNMPv3 traps:
   a) Extract username from trap header
   b) If username in credentials_dict:
      - Get SNMPv3CredentialSet for this username
      - Call get_active_credentials() to get list sorted by priority
      - Try each credential in order:
        * Attempt decryption with auth_type, auth_password, priv_type, priv_password
        * If successful: 
          - Call auth_failure_tracker.clear_failure(username)
          - Return SNMPTrap with snmp_version='v3'
        * If failed: continue to next credential
      - If all credentials fail:
        * Call auth_failure_tracker.record_failure(username, source_hostname)
        * Log: "[SNMPListener] Failed to decrypt v3 trap from {source_hostname} with username {username}"
        * Return SNMPTrap with snmp_version='v3_failed' and error info
   
   c) If username NOT in credentials_dict:
      - Log warning: "[SNMPListener] No credentials found for username {username}"
      - Record failure
      - Return SNMPTrap with snmp_version='v3_unknown_user'

3. For v2c/v1 traps: behavior unchanged

Make sure pysnmp-lextudio is used for v3 decryption support.
```

---

## Patch 7: Update MessageProcessor for Auth Failure Tracker

**File:** `mutt/processors/message_processor.py` (UPDATE)

**Prompt for Gemini:**

```
Update mutt/processors/message_processor.py to initialize AuthFailureTracker:

1. In imports, add: from mutt.storage.auth_failure_tracker import AuthFailureTracker

2. In __init__:
   - After self.database = Database(config)
   - Add: self.auth_failure_tracker = AuthFailureTracker(self.database)

3. This auth_failure_tracker will be passed to SNMPListener later in daemon.py
```

---

## Patch 8: Update MUTTDaemon for Credentials

**File:** `mutt/daemon.py` (UPDATE)

**Prompt for Gemini:**

```
Update mutt/daemon.py MUTTDaemon class:

1. In imports add: from mutt.config import CredentialLoader

2. In __init__, after loading mutt_config.yaml, add:
   - Load credentials: credentials_path = './config/snmpv3_credentials.yaml'
   - self.credentials = CredentialLoader.load_credentials(credentials_path)
   - Log: "[MUTTDaemon] Loaded SNMPv3 credentials"

3. When creating SNMPListener, pass two new arguments:
   - credentials_dict=self.credentials (pass loaded credentials)
   - auth_failure_tracker=self.processor.auth_failure_tracker (pass tracker)
   
   So SNMPListener init call looks like:
   snmp_listener = SNMPListener(
       self.processor.queue,
       self.config,
       credentials_dict=self.credentials,
       auth_failure_tracker=self.processor.auth_failure_tracker
   )

4. This ensures SNMPv3 traps can be decrypted and failures tracked.
```

---

## Patch 9: Update requirements.txt

**File:** `requirements.txt` (UPDATE)

**Prompt for Gemini:**

```
Update requirements.txt to use pysnmp-lextudio instead of pysnmp:

Change:
pysnmp==...

To:
pysnmp-lextudio==1.0.0

This is the modern fork that supports SNMPv1, v2c, and v3 properly.
Keep all other dependencies the same.
```

---

## Patch 10: Create Web UI Interface for Auth Failures (Optional)

**File:** `mutt/storage/database.py` (UPDATE - add method)

**Prompt for Gemini:**

```
Add this method to Database class in mutt/storage/database.py:

async def get_snmpv3_auth_failures(self) -> List[dict]:
    """Get all SNMPv3 authentication failures for web UI display"""
    if not self.db:
        return []
    
    try:
        cursor = await self.db.execute("""
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
        print(f"[Database] Error fetching auth failures: {e}")
        return []

This allows web UI to display a dashboard of auth failures.
```

---

## Testing the Patches

After all patches are applied, test:

### Test 1: Config loading
```bash
python -c "from mutt.config import CredentialLoader; creds = CredentialLoader.load_credentials('./config/snmpv3_credentials.yaml'); print(f'Loaded {len(creds)} credential sets')"
```

### Test 2: Database schema
```bash
python -c "from mutt.storage.schema import SCHEMA; assert 'snmpv3_auth_failures' in SCHEMA; print('Schema OK')"
```

### Test 3: All imports
```bash
python -c "from mutt.daemon import MUTTDaemon; print('All imports OK')"
```

### Test 4: Daemon startup (30 second test)
```bash
timeout 30 python -m mutt.daemon || true
# Should start without errors, listening on ports 5162 and 5514
```

### Test 5: Send test data
```bash
# In one terminal:
python -m mutt.daemon &

# In another terminal:
echo "<14>Jan 10 12:00:00 testhost test: Hello" | nc -u -w0 127.0.0.1 5514
sleep 2
sqlite3 data/messages.db "SELECT COUNT(*) FROM messages WHERE type='SYSLOG';"

# Should show 1 or more SYSLOG messages
```

---

## Rollback Plan

If issues occur:

1. **Config issues:** Just delete/recreate config/snmpv3_credentials.yaml
2. **Database issues:** Delete data/messages.db (next run recreates it)
3. **Code issues:** Revert individual patches, test incrementally
4. **Complete rollback:** Use git to revert to pre-patch state

---

## Deployment Checklist

- [ ] Patch 1: Credentials models created
- [ ] Patch 2: CredentialLoader added to config.py
- [ ] Patch 3: snmpv3_credentials.yaml created
- [ ] Patch 4: Auth failures table added to schema
- [ ] Patch 5: AuthFailureTracker class created
- [ ] Patch 6: SNMPListener updated for v3
- [ ] Patch 7: MessageProcessor updated
- [ ] Patch 8: MUTTDaemon updated
- [ ] Patch 9: requirements.txt updated
- [ ] All tests passing
- [ ] Daemon starts cleanly
- [ ] Test data flows through system

---

## Key Points for Gemini

1. **Maintain existing code** - Only add/modify as specified
2. **Type hints** - Add type hints to all new methods
3. **Async/await** - All database operations must be async
4. **Error handling** - Graceful degradation, never crash on bad creds
5. **Logging** - Clear log messages for debugging
6. **No breaking changes** - Existing code paths should work unchanged

---

**End of Patch Guide**

Feed these patches to Gemini sequentially, testing after each one before moving to the next.
