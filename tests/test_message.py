import unittest
from datetime import datetime
from mutt.models.message import Message, SyslogMessage, SNMPTrap, MessageType, Severity

class TestMessage(unittest.TestCase):
    def test_message_creation(self):
        msg = Message(
            source_ip="127.0.0.1",
            message_type=MessageType.UNKNOWN,
            severity=Severity.INFO,
            payload="test"
        )
        self.assertEqual(msg.source_ip, "127.0.0.1")
        self.assertIsInstance(msg.id, str)
        self.assertIsInstance(msg.timestamp, datetime)

    def test_syslog_message(self):
        msg = SyslogMessage(
            source_ip="127.0.0.1",
            message_type=MessageType.SYSLOG,
            severity=Severity.ERROR,
            payload="error",
            facility=1,
            priority=1,
            hostname="host"
        )
        self.assertEqual(msg.facility, 1)
        self.assertEqual(msg.hostname, "host")

    def test_snmp_trap(self):
        msg = SNMPTrap(
            source_ip="127.0.0.1",
            message_type=MessageType.SNMP_TRAP,
            severity=Severity.WARNING,
            payload="trap",
            oid="1.2.3",
            varbinds={"key": "value"},
            version="v2c"
        )
        self.assertEqual(msg.oid, "1.2.3")
        self.assertEqual(msg.varbinds["key"], "value")

if __name__ == "__main__":
    unittest.main()
