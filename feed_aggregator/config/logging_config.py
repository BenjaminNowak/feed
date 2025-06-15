"""Configure logging for the feed aggregator."""
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path


def setup_logging(name: str = None) -> logging.Logger:
    """Set up logging configuration.

    Args:
        name: Optional name for the logger. If None, returns root logger.

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"feed_aggregator_{timestamp}.log"

    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_formatter = logging.Formatter("%(levelname)s - %(message)s")

    # Create and configure file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10485760, backupCount=5  # 10MB
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Create and configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Set level before formatter
    console_handler.setFormatter(console_formatter)

    # Get logger and configure base level
    logger = logging.getLogger(name) if name else logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Remove any existing handlers to avoid duplicates
    logger.handlers = []

    # Add handlers in order: file first, then console
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
