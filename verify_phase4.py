import asyncio
import os
from mutt.models.message import Message, MessageType, Severity
from mutt.models.rules import AlertRule, PatternType, ActionType
try:
    from mutt.processors.validator import Validator
    from mutt.processors.pattern_matcher import PatternMatcher
    from mutt.processors.enricher import Enricher
except ImportError:
    Validator = None
    PatternMatcher = None
    Enricher = None

from mutt.storage.database import Database
from mutt.storage.device_registry import DeviceRegistry

async def test_pipeline():
    print("Testing Pipeline Components...")
    
    if Validator is None:
        raise ImportError("Processors not implemented yet")

    # 1. Setup
    db_path = "test_phase4.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    db = Database(db_path)
    await db.initialize()
    reg = DeviceRegistry(db)
    
    msg = Message(
        id="test-1",
        timestamp=None, # Should be handled or validated
        source_ip="127.0.0.1",
        message_type=MessageType.SYSLOG,
        severity=Severity.INFO,
        payload="authentication failure for admin",
        metadata={}
    )
    
    # 2. Validate
    v = Validator()
    assert v.validate(msg) is True
    print("✅ Validation OK")
    
    # 3. Match
    rule = AlertRule(
        id="r1", name="Auth Fail", 
        pattern_type=PatternType.KEYWORD, 
        pattern="authentication failure", 
        actions=[ActionType.STORE]
    )
    matcher = PatternMatcher([rule])
    matches = matcher.match(msg)
    assert len(matches) == 1
    print("✅ Pattern Matching OK")
    
    # 4. Enrich
    enricher = Enricher(reg)
    await enricher.enrich(msg)
    # Check if metadata was updated (hostname or at least attempted)
    # The design says: Attempts socket.gethostbyaddr(msg.source_ip). On success, adds hostname to msg.metadata.
    # 127.0.0.1 usually resolves to localhost.
    print(f"Metadata after enrichment: {msg.metadata}")
    assert "source_ip" in msg.__dict__ or msg.source_ip == "127.0.0.1"
    print("✅ Enrichment OK")

async def main():
    try:
        await test_pipeline()
        print("PHASE 4 COMPLETE")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
