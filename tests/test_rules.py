import unittest
from mutt.models.rules import AlertRule, PatternType, ActionType

class TestRules(unittest.TestCase):
    def test_rule_creation(self):
        rule = AlertRule(
            id="1",
            name="test rule",
            pattern_type=PatternType.KEYWORD,
            pattern="error",
            actions=[ActionType.STORE]
        )
        self.assertEqual(rule.name, "test rule")
        self.assertTrue(rule.enabled)

    def test_rule_disabled(self):
        rule = AlertRule(
            id="2",
            name="disabled rule",
            pattern_type=PatternType.REGEX,
            pattern=".*",
            actions=[ActionType.DISCARD],
            enabled=False
        )
        self.assertFalse(rule.enabled)

if __name__ == "__main__":
    unittest.main()
