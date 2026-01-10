import re
from typing import List

from mutt.models.message import Message
from mutt.models.rules import AlertRule, PatternType


class PatternMatcher:
    """
    Matches messages against alert rules based on different pattern types.
    """
    
    def __init__(self, rules: List[AlertRule]):
        """
        Initialize the PatternMatcher with a list of alert rules.
        
        Args:
            rules: List of AlertRule objects to match against
        """
        self.rules = rules
    
    def match(self, msg: Message) -> List[AlertRule]:
        """
        Match a message against all enabled rules.
        
        Args:
            msg: The message to match against rules
            
        Returns:
            List of AlertRule objects that match the message
        """
        matching_rules = []
        
        for rule in self.rules:
            # Skip disabled rules
            if not rule.enabled:
                continue
            
            # Skip rules without a pattern
            if not rule.pattern:
                continue
            
            # Match based on pattern type
            if rule.pattern_type == PatternType.REGEX:
                if re.search(rule.pattern, msg.payload, re.IGNORECASE):
                    matching_rules.append(rule)
                    
            elif rule.pattern_type == PatternType.KEYWORD:
                if rule.pattern.lower() in msg.payload.lower():
                    matching_rules.append(rule)
                    
            elif rule.pattern_type == PatternType.EXACT:
                if rule.pattern == msg.payload:
                    matching_rules.append(rule)
                    
            # Handle unknown pattern types
            else:
                continue
        
        return matching_rules
