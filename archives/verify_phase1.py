import sys
from datetime import datetime
from mutt.models.message import Message, SyslogMessage, MessageType, Severity
from mutt.models.rules import AlertRule, PatternType
from mutt.config import load_config

def test_models():
    print("Testing Models...")
    msg = SyslogMessage(
        id="123",
        timestamp=datetime.utcnow(),
        source_ip="192.168.1.1",
        message_type=MessageType.SYSLOG,
        severity=Severity.ERROR,
        payload="Test failure",
        metadata={},
        facility=1,
        priority=1,
        hostname="router01",
        process_name="sshd",
        process_id=100
    )
    assert msg.severity == Severity.ERROR
    print("✅ Models OK")

def test_config():
    print("Testing Config...")
    try:
        import yaml
        cfg = load_config("config/mutt_config.yaml")
        assert cfg['network']['syslog_port'] == 5514
        print("✅ Config OK")
    except ImportError:
        print("⚠️  Skipping Config test (yaml not installed)")

if __name__ == "__main__":
    try:
        test_models()
        test_config()
        print("PHASE 1 COMPLETE")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)
