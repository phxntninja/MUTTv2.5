import unittest
import asyncio
from mutt.listeners.snmp_listener import SNMPListener
from mutt.models.message import SNMPTrap

class TestSNMPListener(unittest.IsolatedAsyncioTestCase):
    async def test_process_data(self):
        queue = asyncio.Queue()
        listener = SNMPListener(queue)
        
        raw_data = b"\x30\x0e\x02\x01\x01\x04\x06\x70\x75\x62\x6c\x69\x63" # Dummy ASN.1
        listener.process_data(raw_data, ("127.0.0.1", 12345))
        
        msg = queue.get_nowait()
        self.assertIsInstance(msg, SNMPTrap)
        self.assertEqual(msg.source_ip, "127.0.0.1")
        self.assertEqual(msg.payload, "SNMP Trap Received (Parsing pending)")

if __name__ == '__main__':
    unittest.main()
