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
    
    try:
        from mutt import MUTTDaemon, load_config
        print("✅ MUTTDaemon and load_config importable from mutt")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        raise
    
    print("PHASE 6 PRE-CHECK COMPLETE. Now run: pytest tests/test_integration.py")

if __name__ == "__main__":
    asyncio.run(main())
