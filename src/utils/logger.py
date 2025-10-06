"""
Logging Utility Module
~~~~~~~~~~~~~~~~~~~~~~

Configures and provides logging functionality.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "wellfound_scraper",
    log_dir: str = "./logs",
    log_level: str = "INFO",
    console_output: bool = True,
    log_format: Optional[str] = None,
    date_format: Optional[str] = None,
) -> logging.Logger:
    """
    Set up and configure logger.

    Args:
        name: Logger name
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Whether to output to console
        log_format: Custom log format string
        date_format: Custom date format string

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Default formats
    if log_format is None:
        log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    if date_format is None:
        date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(log_format, datefmt=date_format)

    # File handler
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir_path / f"scraper_{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # Capture all levels in file
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    logger.info(f"Logger initialized. Log file: {log_file}")

    return logger


class LoggerMixin:
    """Mixin class to add logging capability to any class."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        if not hasattr(self, "_logger"):
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger
