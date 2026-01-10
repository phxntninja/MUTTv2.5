"""
Logging configuration for mutt.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    import colorama
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


def setup_logging(log_file: str, debug: bool = False) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        log_file: Path to the log file where logs will be written.
        debug: If True, set log level to DEBUG, otherwise INFO.
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize colorama for colored console output
    if COLORAMA_AVAILABLE:
        colorama.init()
    
    # Determine log level
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # File handler for logging to file
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler with colored output
    console_handler = _create_console_handler(log_level, formatter)
    root_logger.addHandler(console_handler)
    
    # Log the logging setup
    root_logger.debug(f"Logging initialized. Level: {logging.getLevelName(log_level)}")
    root_logger.debug(f"Log file: {log_file}")
    root_logger.debug(f"Colorama available: {COLORAMA_AVAILABLE}")


def _create_console_handler(level: int, formatter: logging.Formatter) -> logging.Handler:
    """
    Create a console handler with optional colored output.
    
    Args:
        level: Logging level for the handler.
        formatter: Formatter to use for the handler.
        
    Returns:
        Configured console handler.
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if COLORAMA_AVAILABLE:
        # Create colored formatter for console
        class ColoredFormatter(logging.Formatter):
            """Custom formatter that adds colors to log levels."""
            
            # Color codes
            COLORS = {
                'DEBUG': colorama.Fore.CYAN,
                'INFO': colorama.Fore.GREEN,
                'WARNING': colorama.Fore.YELLOW,
                'ERROR': colorama.Fore.RED,
                'CRITICAL': colorama.Fore.RED + colorama.Style.BRIGHT,
            }
            
            RESET = colorama.Style.RESET_ALL
            
            def format(self, record):
                # Format the message using the parent formatter
                formatted_message = super().format(record)
                
                # Add color to the levelname
                if record.levelname in self.COLORS:
                    # Find the levelname in the formatted message and colorize it
                    level_str = f"| {record.levelname} |"
                    colored_level = f"{self.COLORS[record.levelname]}{level_str}{self.RESET}"
                    formatted_message = formatted_message.replace(level_str, colored_level)
                
                return formatted_message
        
        colored_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(colored_formatter)
    else:
        console_handler.setFormatter(formatter)
    
    return console_handler


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Name for the logger (typically __name__).
        
    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
