import asyncio
import os
from datetime import datetime
from mutt.models.message import Message, MessageType, Severity
from mutt.storage.database import Database
from mutt.storage.device_registry import DeviceRegistry

DB_PATH = "test_phase2.db"

async def test_database():
    print("Testing Database...")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    db = Database(DB_PATH)
    await db.initialize()
    
    # Store a message
    msg = Message(
        id="test-uuid-1",
        timestamp=datetime.utcnow(),
        source_ip="10.0.0.1",
        message_type=MessageType.SYSLOG,
        severity=Severity.INFO,
        payload="Test Payload",
        metadata={"foo": "bar"}
    )
    await db.store_message(msg)
    
    # Retrieve
    msgs = await db.get_messages()
    assert len(msgs) == 1
    assert msgs[0].payload == "Test Payload"
    assert msgs[0].metadata["foo"] == "bar"
    print("✅ Database Store/Load OK")
    return db

async def test_registry(db):
    print("Testing Device Registry...")
    reg = DeviceRegistry(db)
    await reg.update_device("10.0.0.1", hostname="switch01")
    
    # Verify in raw DB
    async with db.pool.execute("SELECT hostname FROM devices WHERE ip='10.0.0.1'") as cursor:
        row = await cursor.fetchone()
        assert row[0] == "switch01"
    print("✅ Registry OK")

async def main():
    try:
        db = await test_database()
        await test_registry(db)
        print("PHASE 2 COMPLETE")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
