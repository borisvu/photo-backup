"""Test logger module."""

import logging
import pytest
from io import StringIO
import sys
from photo_backup.logger import setup_logger, get_logger, set_log_level


def test_logger_import():
    """Test that logger functions can be imported."""
    assert setup_logger is not None
    assert get_logger is not None
    assert set_log_level is not None


def test_setup_logger_basic():
    """Test basic logger setup."""
    logger = setup_logger("test_basic")
    
    assert logger is not None
    assert logger.name == "test_basic"
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_setup_logger_with_level():
    """Test logger setup with custom level."""
    logger = setup_logger("test_debug", logging.DEBUG)
    
    assert logger.level == logging.DEBUG
    assert logger.handlers[0].level == logging.DEBUG


def test_logger_output(capsys):
    """Test that logger actually outputs messages."""
    logger = setup_logger("test_output", logging.INFO)
    
    logger.info("Test message")
    
    captured = capsys.readouterr()
    assert "Test message" in captured.out
    assert "test_output" in captured.out
    assert "INFO" in captured.out


def test_logger_levels(capsys):
    """Test different log levels."""
    logger = setup_logger("test_levels", logging.DEBUG)
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")
    
    captured = capsys.readouterr()
    assert "Debug message" in captured.out
    assert "Info message" in captured.out
    assert "Warning message" in captured.out
    assert "Error message" in captured.out
    assert "Critical message" in captured.out


def test_logger_level_filtering(capsys):
    """Test that log level filtering works."""
    logger = setup_logger("test_filter", logging.WARNING)
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    
    captured = capsys.readouterr()
    assert "Debug message" not in captured.out
    assert "Info message" not in captured.out
    assert "Warning message" in captured.out
    assert "Error message" in captured.out


def test_get_logger():
    """Test get_logger function."""
    # Create a logger first
    original = setup_logger("test_get")
    
    # Get the same logger
    retrieved = get_logger("test_get")
    
    assert retrieved is original
    assert retrieved.name == "test_get"


def test_get_logger_default():
    """Test get_logger with default name."""
    logger = get_logger()
    assert logger.name == "photo_backup"


def test_set_log_level():
    """Test changing log level."""
    logger = setup_logger("test_level_change", logging.INFO)
    
    # Change to DEBUG
    set_log_level(logging.DEBUG, "test_level_change")
    
    assert logger.level == logging.DEBUG
    assert logger.handlers[0].level == logging.DEBUG


def test_no_duplicate_handlers():
    """Test that calling setup_logger twice doesn't add duplicate handlers."""
    logger1 = setup_logger("test_duplicate")
    logger2 = setup_logger("test_duplicate")
    
    assert logger1 is logger2
    assert len(logger1.handlers) == 1


def test_logger_timestamp_format(capsys):
    """Test that logger includes timestamp in correct format."""
    logger = setup_logger("test_timestamp", logging.INFO)
    
    logger.info("Timestamp test")
    
    captured = capsys.readouterr()
    # Check for timestamp pattern (YYYY-MM-DD HH:MM:SS)
    import re
    timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
    assert re.search(timestamp_pattern, captured.out) is not None


def test_logger_no_propagation():
    """Test that logger doesn't propagate to root logger."""
    logger = setup_logger("test_propagation")
    assert logger.propagate is False