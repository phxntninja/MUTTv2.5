import unittest
import asyncio
from mutt.listeners.base import BaseListener

class TestBaseListener(unittest.TestCase):
    def test_cannot_instantiate_base_listener_directly(self):
        with self.assertRaises(TypeError):
            BaseListener(queue=asyncio.Queue())

    def test_concrete_implementation(self):
        class ConcreteListener(BaseListener):
            async def start(self):
                self._is_running = True
            async def stop(self):
                self._is_running = False
            def process_data(self, data, addr):
                pass
        
        queue = asyncio.Queue()
        listener = ConcreteListener(queue)
        self.assertEqual(listener.queue, queue)
        self.assertFalse(listener.is_running)

if __name__ == '__main__':
    unittest.main()
