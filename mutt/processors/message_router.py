import asyncio
from typing import Callable, Dict, List, Set
from collections import defaultdict

from mutt.models.message import Message
from mutt.models.rules import AlertRule, ActionType


class MessageRouter:
    """Routes messages to appropriate handlers based on action types."""
    
    def __init__(self):
        """Initialize the message router with empty handler registry."""
        self._handlers: Dict[ActionType, Callable] = {}
    
    def register_handler(self, action: ActionType, handler: Callable) -> None:
        """
        Register an async handler function for a specific action type.
        
        Args:
            action: The action type to register the handler for
            handler: Async function that takes (Message, List[AlertRule]) as arguments
        """
        self._handlers[action] = handler
    
    async def route(self, msg: Message, rules: List[AlertRule]) -> None:
        """
        Route a message to handlers based on matching rules' action types.
        
        Args:
            msg: The message to route
            rules: List of alert rules that matched the message
        """
        if not rules:
            return
        
        # Group rules by their action types
        # A single rule can have multiple actions
        rules_by_action = defaultdict(list)
        for rule in rules:
            for action in rule.actions:
                rules_by_action[action].append(rule)
        
        # Prepare handler calls for each unique action type
        tasks = []
        for action_type, action_rules in rules_by_action.items():
            handler = self._handlers.get(action_type)
            if handler:
                # Call handler with message and rules for this specific action
                tasks.append(handler(msg, action_rules))
        
        # Execute all handlers concurrently
        if tasks:
            await asyncio.gather(*tasks)
