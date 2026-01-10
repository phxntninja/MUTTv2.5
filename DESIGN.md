# MUTT 2.5 - Phase 6: Integration & Glue

## Context
Phases 1-5 are complete.
Phase 6 Focus: **Final Assembly**.
We are creating the entry point script, package initialization, and a full integration test.

## detailed Implementation Requirements

### 1. `mutt/__init__.py`
*   Expose `MUTTDaemon` and `load_config`.

### 2. `run.sh`
*   Bash script.
*   Resolves directory.
*   Activates `.venv` if it exists.
*   Executes `python3 -m mutt.daemon --config config/mutt_config.yaml`.
*   Make it executable (`chmod +x`).

### 3. `tests/test_integration.py`
A comprehensive test that mimics a real deployment.
*   Creates a temporary `mutt_config_test.yaml`.
*   Starts `MUTTDaemon` in a background task/thread.
*   Sends a UDP Syslog packet to localhost:5514.
*   Waits 2 seconds.
*   Checks `data/messages.db` (or test db) to see if the message arrived.
*   Stops the Daemon.

## TDD / Verification Strategy

**Script: `verify_phase6.py`**
```python
import os
import subprocess
import time
import asyncio
import sqlite3

async def main():
    print("Testing Full Integration...")
    
    # 1. Ensure run.sh exists
    if not os.path.exists("run.sh"):
        raise FileNotFoundError("run.sh not found")
        
    # 2. Run Integration Test (We delegate to the pytest file we are creating)
    # But for this verification script, we just check imports and file presence
    
    from mutt import MUTTDaemon
    print("✅ MUTTDaemon importable")
    
    print("PHASE 6 PRE-CHECK COMPLETE. Now run: pytest tests/test_integration.py")

if __name__ == "__main__":
    asyncio.run(main())
```

## Execution Steps
1.  Run `verify_phase6.py` (Fails).
2.  Create `mutt/__init__.py`.
3.  Create `run.sh`.
4.  Create `tests/test_integration.py`.
5.  Run `verify_phase6.py` (Passes).