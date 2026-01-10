import unittest
import asyncio
from mutt.listeners.syslog_listener import SyslogListener
from mutt.models.message import Severity, SyslogMessage

class TestSyslogListener(unittest.IsolatedAsyncioTestCase):
    async def test_parse_valid_rfc3164_message(self):
        queue = asyncio.Queue()
        listener = SyslogListener(queue)
        
        # <134>Jan 09 20:30:00 myhost myproc: test message
        raw_msg = "<134>Jan 09 20:30:00 myhost myproc: test message"
        msg = listener._parse_syslog_message(raw_msg, "127.0.0.1")
        
        self.assertIsInstance(msg, SyslogMessage)
        self.assertEqual(msg.priority, 134)
        self.assertEqual(msg.facility, 16)
        self.assertEqual(msg.severity, Severity.INFO)
        self.assertEqual(msg.hostname, "myhost")
        self.assertEqual(msg.process_name, "myproc")
        self.assertEqual(msg.payload, "test message")

    async def test_parse_invalid_message_fallback(self):
        queue = asyncio.Queue()
        listener = SyslogListener(queue)
        
        raw_msg = "invalid message"
        msg = listener._parse_syslog_message(raw_msg, "127.0.0.1")
        
        self.assertIsInstance(msg, SyslogMessage)
        self.assertEqual(msg.hostname, "unknown")
        self.assertEqual(msg.payload, "invalid message")
        self.assertEqual(msg.severity, Severity.INFO)

    async def test_process_data(self):
        queue = asyncio.Queue()
        listener = SyslogListener(queue)
        
        raw_msg = b"<134>Jan 09 20:30:00 myhost myproc: test message"
        listener.process_data(raw_msg, ("127.0.0.1", 12345))
        
        msg = queue.get_nowait()
        self.assertEqual(msg.payload, "test message")

if __name__ == '__main__':
    unittest.main()
