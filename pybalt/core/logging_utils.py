import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import os

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
    name: str, level: int = logging.INFO, debug: bool = False, include_timestamp: bool = True, force_console: bool = False, config=None
) -> logging.Logger:
    """
    Configure a logger with colored output and optional file logging

    Args:
        name: Logger name
        level: Initial logging level
        debug: If True, set level to DEBUG
        include_timestamp: Include timestamp in log format
        force_console: Force adding a console handler even if handlers exist
        config: Config object for file logging settings

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Set level based on debug flag or provided level
    logger.setLevel(logging.DEBUG if debug else level)

    # Only add handlers if it doesn't have any or force_console is True
    if not logger.handlers or force_console:
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if debug else level)

        # Create and set formatter
        formatter = ColoredFormatter(include_timestamp=include_timestamp)
        console_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(console_handler)

        # Add file handler if config is provided and file logging is enabled
        if config and config.get("enable_file_logging", True, "logging"):
            try:
                _add_file_handler(logger, config, debug)
            except Exception as e:
                logger.warning(f"Failed to setup file logging: {e}")

    return logger


def _add_file_handler(logger: logging.Logger, config, debug: bool = False):
    """
    Add a rotating file handler to the logger.

    Args:
        logger: Logger instance to add handler to
        config: Config object for settings
        debug: Debug mode flag
    """
    # Get log folder and ensure it exists
    log_folder = config.get_log_folder()
    try:
        log_folder.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        logger.warning(f"Cannot create log directory {log_folder}: {e}")
        return

    # Create log file path
    log_file = log_folder / "pybalt.log"

    # Get file logging settings
    max_size_mb = config.get_as_number("max_log_size_mb", fallback=10, section="logging")
    max_files = config.get_as_number("max_log_files", fallback=5, section="logging")
    log_level_str = config.get("log_level", fallback="INFO", section="logging").upper()

    # Convert log level string to logging level
    log_level = getattr(logging, log_level_str, logging.INFO)
    if debug:
        log_level = logging.DEBUG

    try:
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=int(max_size_mb * 1024 * 1024),  # Convert MB to bytes
            backupCount=int(max_files),
        )
        file_handler.setLevel(log_level)

        # Get format settings from config
        log_format = config.get("log_format", fallback="%(asctime)s - %(name)s - %(levelname)s - %(message)s", section="logging")
        date_format = config.get("date_format", fallback="%Y-%m-%d %H:%M:%S", section="logging")
        include_timestamp = config.get("include_timestamp", fallback=True, section="logging")

        # Create file formatter (no colors for file output)
        if include_timestamp:
            file_formatter = logging.Formatter(log_format, datefmt=date_format)
        else:
            # Remove timestamp from format if disabled
            simple_format = log_format.replace("%(asctime)s - ", "")
            file_formatter = logging.Formatter(simple_format)

        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        logger.debug(f"File logging enabled: {log_file} (max {max_size_mb}MB, {max_files} files)")

    except (PermissionError, OSError) as e:
        logger.warning(f"Cannot create log file {log_file}: {e}")
    except Exception as e:
        logger.warning(f"Failed to setup file handler: {e}")


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
        try:
            from .config import Config

            config = Config()
        except ImportError:
            # Fallback if config import fails
            config = None

    # Determine debug mode
    debug_mode = debug
    if debug_mode is None and config:
        debug_mode = config.get("debug", False, "general")
    elif debug_mode is None:
        debug_mode = False

    return setup_logger(name, debug=debug_mode, config=config)
