"""
MUTT - Multi-User Testing Tool

A framework for managing and executing automated tests across multiple users.
"""

from .daemon import MUTTDaemon
from .config import load_config

__version__ = "1.0.0"
__all__ = ["MUTTDaemon", "load_config"]
