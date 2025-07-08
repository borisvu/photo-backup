"""
Unit tests for logger module.

These tests focus on logging functionality in isolation.
"""

import logging
import pytest
from photo_backup.logger import setup_logger


class TestLogger:
    """Test cases for logger setup and configuration."""
    
    @pytest.mark.unit
    def test_setup_logger_default_params(self):
        """Test logger setup with default parameters."""
        logger = setup_logger("test_default")
        
        assert logger.name == "test_default"
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0
    
    @pytest.mark.unit
    def test_setup_logger_custom_name(self):
        """Test logger setup with custom name."""
        custom_name = "test_custom_name"
        logger = setup_logger(name=custom_name)
        
        assert logger.name == custom_name
        assert logger.level == logging.INFO
    
    @pytest.mark.unit
    def test_setup_logger_debug_level(self):
        """Test logger setup with DEBUG level."""
        logger = setup_logger("test_debug", logging.DEBUG)
        
        assert logger.level == logging.DEBUG
    
    @pytest.mark.unit
    def test_setup_logger_warning_level(self):
        """Test logger setup with WARNING level."""
        logger = setup_logger("test_warning", logging.WARNING)
        
        assert logger.level == logging.WARNING
    
    @pytest.mark.unit
    def test_setup_logger_error_level(self):
        """Test logger setup with ERROR level."""
        logger = setup_logger("test_error", logging.ERROR)
        
        assert logger.level == logging.ERROR
    
    @pytest.mark.unit
    def test_logger_has_console_handler(self):
        """Test that logger has a console handler configured."""
        logger = setup_logger("test_console")
        
        # Should have at least one handler
        assert len(logger.handlers) > 0
        
        # Should have a StreamHandler (console handler)
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) > 0
    
    @pytest.mark.unit
    def test_logger_formatter_includes_timestamp(self):
        """Test that logger formatter includes timestamp."""
        logger = setup_logger("test_formatter")
        
        # Get the formatter from the first handler
        handler = logger.handlers[0]
        formatter = handler.formatter
        
        assert formatter is not None
        
        # Check that the format string includes timestamp components
        format_string = formatter._fmt
        assert "%(asctime)s" in format_string
        assert "%(name)s" in format_string
        assert "%(levelname)s" in format_string
        assert "%(message)s" in format_string
    
    @pytest.mark.unit
    def test_logger_multiple_instances_same_name(self):
        """Test that multiple logger instances with same name are the same object."""
        logger1 = setup_logger("same_name_test")
        logger2 = setup_logger("same_name_test")
        
        # Should be the same logger instance
        assert logger1 is logger2
    
    @pytest.mark.unit
    def test_logger_different_names_different_instances(self):
        """Test that loggers with different names are different instances."""
        logger1 = setup_logger("logger_one_test")
        logger2 = setup_logger("logger_two_test")
        
        # Should be different logger instances
        assert logger1 is not logger2
        assert logger1.name != logger2.name
    
    @pytest.mark.unit
    def test_logger_no_propagation(self):
        """Test that logger doesn't propagate to avoid duplicate messages."""
        logger = setup_logger("test_propagation")
        
        # Should not propagate to root logger
        assert logger.propagate is False
    
    @pytest.mark.unit
    def test_logger_can_log_messages_with_caplog(self, caplog):
        """Test that logger can log messages (captured by caplog)."""
        # Use a unique logger name for this test
        logger_name = "test_caplog_unique"
        
        # Clear any existing handlers to ensure clean state
        test_logger = logging.getLogger(logger_name)
        test_logger.handlers.clear()
        test_logger.propagate = True  # Enable propagation for caplog
        
        # Set up logger with propagation enabled
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        
        test_message = "Test log message for caplog"
        
        with caplog.at_level(logging.DEBUG, logger=logger_name):
            logger.debug(test_message)
            logger.info(test_message)
            logger.warning(test_message)
            logger.error(test_message)
        
        # Check that messages were logged
        assert len(caplog.records) == 4
        assert all(test_message in record.message for record in caplog.records)
    
    @pytest.mark.unit
    def test_logger_level_setting_works(self):
        """Test that logger level setting works correctly."""
        # Test that different loggers can have different levels
        debug_logger = setup_logger("test_debug_level", logging.DEBUG)
        warning_logger = setup_logger("test_warning_level", logging.WARNING)
        
        assert debug_logger.level == logging.DEBUG
        assert warning_logger.level == logging.WARNING
        
        # Test that the loggers are different instances
        assert debug_logger is not warning_logger
        assert debug_logger.name != warning_logger.name
    
    @pytest.mark.unit
    def test_logger_handler_reuse(self):
        """Test that calling setup_logger multiple times doesn't add duplicate handlers."""
        logger_name = "test_handler_reuse"
        
        # First call
        logger1 = setup_logger(logger_name, logging.INFO)
        handler_count_1 = len(logger1.handlers)
        
        # Second call with same name
        logger2 = setup_logger(logger_name, logging.DEBUG)
        handler_count_2 = len(logger2.handlers)
        
        # Should be same logger and same number of handlers
        assert logger1 is logger2
        assert handler_count_1 == handler_count_2
        assert handler_count_1 == 1  # Should have exactly one handler
    
    @pytest.mark.unit
    def test_logger_level_inheritance(self):
        """Test logger level behavior with parent/child relationships."""
        # Create parent logger
        parent_logger = setup_logger("parent_test", logging.WARNING)
        
        # Create child logger (different name, so different instance)
        child_logger = setup_logger("parent_test.child", logging.DEBUG)
        
        assert parent_logger.level == logging.WARNING
        assert child_logger.level == logging.DEBUG
        assert parent_logger.name != child_logger.name
    
    @pytest.mark.unit
    def test_logger_output_format(self, caplog):
        """Test that logger output has correct format."""
        logger_name = "test_format_unique"
        
        # Set up logger with propagation for caplog
        test_logger = logging.getLogger(logger_name)
        test_logger.handlers.clear()
        test_logger.propagate = True
        test_logger.setLevel(logging.INFO)
        
        test_message = "Format test message"
        
        with caplog.at_level(logging.INFO, logger=logger_name):
            test_logger.info(test_message)
        
        assert len(caplog.records) == 1
        record = caplog.records[0]
        
        assert record.name == logger_name
        assert record.levelname == "INFO"
        assert record.message == test_message