import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock
from mutt.models.message import Message, MessageType, Severity
from mutt.models.rules import AlertRule, PatternType, ActionType
from mutt.processors.validator import Validator
from mutt.processors.pattern_matcher import PatternMatcher
from mutt.processors.enricher import Enricher
from mutt.processors.message_router import MessageRouter

class TestProcessors(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.msg = Message(
            source_ip="127.0.0.1",
            message_type=MessageType.SYSLOG,
            severity=Severity.INFO,
            payload="authentication failure for admin",
            metadata={}
        )

    def test_validator(self):
        v = Validator()
        self.assertTrue(v.validate(self.msg))
        
        invalid_msg = Message(
            source_ip="",
            message_type=MessageType.SYSLOG,
            severity=Severity.INFO,
            payload="",
            metadata={}
        )
        self.assertFalse(v.validate(invalid_msg))
        self.assertIn("Missing required field: source_ip", invalid_msg.metadata["validation_errors"])
        self.assertIn("Payload cannot be empty", invalid_msg.metadata["validation_errors"])

    def test_pattern_matcher(self):
        rule1 = AlertRule(
            id="r1", name="Auth Fail", 
            pattern_type=PatternType.KEYWORD, 
            pattern="authentication failure", 
            actions=[ActionType.STORE]
        )
        rule2 = AlertRule(
            id="r2", name="Exact Match", 
            pattern_type=PatternType.EXACT, 
            pattern="authentication failure for admin", 
            actions=[ActionType.WEBHOOK]
        )
        rule3 = AlertRule(
            id="r3", name="Regex Match", 
            pattern_type=PatternType.REGEX, 
            pattern=r"auth.*failure", 
            actions=[ActionType.STORE]
        )
        rule4 = AlertRule(
            id="r4", name="No Match", 
            pattern_type=PatternType.KEYWORD, 
            pattern="success", 
            actions=[ActionType.STORE]
        )
        
        matcher = PatternMatcher([rule1, rule2, rule3, rule4])
        matches = matcher.match(self.msg)
        self.assertEqual(len(matches), 3)
        self.assertIn(rule1, matches)
        self.assertIn(rule2, matches)
        self.assertIn(rule3, matches)
        self.assertNotIn(rule4, matches)

    async def test_enricher(self):
        reg = MagicMock()
        reg.update_device = AsyncMock()
        
        enricher = Enricher(reg)
        # We might not have DNS resolution for 127.0.0.1 in sandbox, but it should at least not crash
        await enricher.enrich(self.msg)
        
        reg.update_device.assert_called_once()
        # Check severity normalization
        self.msg.severity = "error"
        await enricher.enrich(self.msg)
        self.assertEqual(self.msg.severity, Severity.ERROR)

    async def test_message_router(self):
        router = MessageRouter()
        
        handler_store = AsyncMock()
        handler_webhook = AsyncMock()
        
        router.register_handler(ActionType.STORE, handler_store)
        router.register_handler(ActionType.WEBHOOK, handler_webhook)
        
        rule1 = AlertRule(id="r1", name="r1", pattern_type=PatternType.KEYWORD, pattern="p1", actions=[ActionType.STORE])
        rule2 = AlertRule(id="r2", name="r2", pattern_type=PatternType.KEYWORD, pattern="p2", actions=[ActionType.STORE, ActionType.WEBHOOK])
        
        await router.route(self.msg, [rule1, rule2])
        
        handler_store.assert_called_once()
        # It should be called with (msg, [rule1, rule2])
        args, kwargs = handler_store.call_args
        self.assertEqual(args[0], self.msg)
        self.assertEqual(len(args[1]), 2)
        
        handler_webhook.assert_called_once()
        args, kwargs = handler_webhook.call_args
        self.assertEqual(args[0], self.msg)
        self.assertEqual(len(args[1]), 1)
        self.assertEqual(args[1][0], rule2)

if __name__ == "__main__":
    unittest.main()
