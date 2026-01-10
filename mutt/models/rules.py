from dataclasses import dataclass, field
from enum import Enum
from typing import List


class PatternType(Enum):
    """Enum representing the type of pattern matching."""
    REGEX = "regex"
    KEYWORD = "keyword"
    EXACT = "exact"


class ActionType(Enum):
    """Enum representing the type of action to take."""
    STORE = "store"
    DISCARD = "discard"
    WEBHOOK = "webhook"


@dataclass
class AlertRule:
    """Dataclass representing an alert rule for log matching."""
    id: str
    name: str
    pattern_type: PatternType
    pattern: str
    actions: List[ActionType]
    enabled: bool = field(default=True)
