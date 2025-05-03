import logging
import sys
from typing import Optional

try:
    import colorama
    from colorama import Fore, Style

    colorama.init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


# Define color constants even if colorama is not available
class DummyColors:
    def __getattr__(self, name):
        return ""


if not HAS_COLORAMA:
    Fore = DummyColors()
    Style = DummyColors()


class ColoredFormatter(logging.Formatter):
    """Custom formatter adding colors to log levels"""

    LEVEL_COLORS = {"DEBUG": Fore.CYAN, "INFO": Fore.GREEN, "WARNING": Fore.YELLOW, "ERROR": Fore.RED, "CRITICAL": Fore.RED + Style.BRIGHT}

    RESET = Style.RESET_ALL if HAS_COLORAMA else ""

    def __init__(self, fmt=None, datefmt=None, style="%", include_timestamp=True):
        self.include_timestamp = include_timestamp
        if include_timestamp:
            fmt = fmt or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        else:
            fmt = fmt or "%(name)s - %(levelname)s - %(message)s"
        super().__init__(fmt, datefmt, style)

    def format(self, record):
        # Make a copy of the record to avoid modifying the original
        copied_record = logging.makeLogRecord(record.__dict__)

        # Add colors to the level name
        levelname = copied_record.levelname
        color = self.LEVEL_COLORS.get(levelname, "")
        module_color = Fore.BLUE
        name_parts = copied_record.name.split(".")

        if len(name_parts) > 1:
            # Format as pybalt.module
            copied_record.name = f"{module_color}{name_parts[0]}{self.RESET}.{Fore.MAGENTA}{'.'.join(name_parts[1:])}{self.RESET}"
        else:
            copied_record.name = f"{module_color}{copied_record.name}{self.RESET}"

        copied_record.levelname = f"{color}{levelname}{self.RESET}"

        # Add indentation for better readability
        copied_record.message = copied_record.getMessage()
        copied_record.msg = f"{color}▶ {self.RESET}{copied_record.msg}"

        return super().format(copied_record)


def setup_logger(
    name: str, level: int = logging.INFO, debug: bool = False, include_timestamp: bool = True, force_console: bool = False
) -> logging.Logger:
    """
    Configure a logger with colored output

    Args:
        name: Logger name
        level: Initial logging level
        debug: If True, set level to DEBUG
        include_timestamp: Include timestamp in log format
        force_console: Force adding a console handler even if handlers exist

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Set level based on debug flag or provided level
    logger.setLevel(logging.DEBUG if debug else level)

    # Only add handler if it doesn't have one or force_console is True
    if not logger.handlers or force_console:
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if debug else level)

        # Create and set formatter
        formatter = ColoredFormatter(include_timestamp=include_timestamp)
        console_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str, debug: Optional[bool] = None, config=None) -> logging.Logger:
    """
    Get a logger with the pybalt configuration applied.

    Args:
        name: Logger name
        debug: Override debug setting
        config: Config object to get debug setting from

    Returns:
        Configured logger instance
    """
    # Import here to avoid circular imports
    if config is None:
        from .config import Config

        config = Config()

    # Determine debug mode
    debug_mode = debug if debug is not None else config.get("debug", False, "general")

    return setup_logger(name, debug=debug_mode)
