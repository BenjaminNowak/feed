"""Test logging configuration."""
import logging
from pathlib import Path

import pytest

from feed_aggregator.config.logging_config import setup_logging


@pytest.fixture
def cleanup_logs():
    """Clean up log files after tests."""
    yield
    log_dir = Path("logs")
    if log_dir.exists():
        for log_file in log_dir.glob("feed_aggregator_*.log"):
            log_file.unlink()
        log_dir.rmdir()


def test_setup_logging_creates_logger(cleanup_logs):
    """Test that setup_logging creates a properly configured logger."""
    logger = setup_logging("test_logger")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger"
    assert logger.level == logging.DEBUG

    # Verify handlers
    assert len(logger.handlers) == 2

    # Check handlers (excluding RotatingFileHandler from StreamHandler check)
    file_handler = next(
        h
        for h in logger.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    )
    assert file_handler.level == logging.DEBUG
    assert isinstance(file_handler.formatter, logging.Formatter)
    assert "%(name)s" in file_handler.formatter._fmt

    # Check console handler (must be instance of StreamHandler but not RotatingFileHandler)
    console_handler = next(
        h
        for h in logger.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.handlers.RotatingFileHandler)
    )
    assert console_handler.level == logging.INFO
    assert isinstance(console_handler.formatter, logging.Formatter)
    assert "%(levelname)s" in console_handler.formatter._fmt


def test_setup_logging_creates_log_directory(cleanup_logs):
    """Test that setup_logging creates the log directory if it doesn't exist."""
    log_dir = Path("logs")
    if log_dir.exists():
        for log_file in log_dir.glob("feed_aggregator_*.log"):
            log_file.unlink()
        log_dir.rmdir()

    setup_logging()
    assert log_dir.exists()
    assert any(log_dir.glob("feed_aggregator_*.log"))


def test_setup_logging_creates_rotating_file_handler(cleanup_logs):
    """Test that setup_logging creates a rotating file handler with correct settings."""
    logger = setup_logging()

    file_handler = next(
        h
        for h in logger.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    )
    assert file_handler.maxBytes == 10485760  # 10MB
    assert file_handler.backupCount == 5


def test_setup_logging_writes_to_file(cleanup_logs):
    """Test that messages are written to the log file."""
    logger = setup_logging("test_file_logger")
    test_message = "Test debug message"
    logger.debug(test_message)

    log_dir = Path("logs")
    log_file = next(log_dir.glob("feed_aggregator_*.log"))

    with open(log_file, "r") as f:
        log_content = f.read()
        assert test_message in log_content
        assert "DEBUG" in log_content
        assert "test_file_logger" in log_content
