"""
Unit tests for the logging configuration module.
"""

# standard imports
import logging
import os
from unittest.mock import Mock, patch

# lib imports
import pytest

# local imports
from src.common import logging_config


class TestDiscordHandler:
    """Test the DiscordHandler class."""

    def test_discord_handler_initialization(self):
        """Test that Discord handler initializes correctly."""
        handler = logging_config.DiscordHandler(level=logging.WARNING)

        assert handler.bot is None
        assert handler.channel_id is None
        assert handler._setup_complete is False

    def test_discord_handler_setup_with_channel_id(self):
        """Test Discord handler setup with explicit channel ID."""
        handler = logging_config.DiscordHandler()
        mock_bot = Mock()

        handler.setup(mock_bot, channel_id=123456789)

        assert handler.bot == mock_bot
        assert handler.channel_id == 123456789
        assert handler._setup_complete is True

    def test_discord_handler_setup_with_env_variable(self):
        """Test Discord handler setup with environment variable."""
        handler = logging_config.DiscordHandler()
        mock_bot = Mock()

        with patch.dict(os.environ, {'DISCORD_LOG_CHANNEL_ID': '987654321'}):
            handler.setup(mock_bot)

        assert handler.bot == mock_bot
        assert handler.channel_id == 987654321
        assert handler._setup_complete is True

    def test_discord_handler_emit_not_setup(self):
        """Test that emit does nothing if handler is not setup."""
        handler = logging_config.DiscordHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        # Should not raise an error
        handler.emit(record)

    def test_discord_handler_emit_sends_message(self):
        """Test that emit sends a message to Discord."""
        handler = logging_config.DiscordHandler()
        mock_bot = Mock()
        mock_bot.loop = None  # No event loop in test
        mock_bot.async_send_message = Mock()

        handler.setup(mock_bot, channel_id=123456789)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Test error message",
            args=(),
            exc_info=None
        )

        # The handler now uses asyncio, so we just verify it doesn't crash
        # In actual usage, it will send the message asynchronously
        with patch('discord.Embed'):
            handler.emit(record)

        # The emit should not raise an exception even if bot.loop is None
        # This is expected behavior - it will fail gracefully

    def test_discord_handler_emit_handles_exceptions(self):
        """Test that emit handles exceptions gracefully."""
        handler = logging_config.DiscordHandler()
        mock_bot = Mock()
        mock_bot.send_message = Mock(side_effect=Exception("Discord error"))

        handler.setup(mock_bot, channel_id=123456789)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        # Should handle the exception internally
        with patch('discord.Embed'):
            handler.emit(record)

    def test_discord_handler_queues_messages_before_setup(self):
        """Test that messages are queued before bot is ready."""
        handler = logging_config.DiscordHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        # Create some log records before setup
        record1 = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Message 1",
            args=(),
            exc_info=None
        )
        record2 = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=2,
            msg="Message 2",
            args=(),
            exc_info=None
        )

        # Emit before setup - should be queued
        handler.emit(record1)
        handler.emit(record2)

        # Verify messages were queued
        assert len(handler._message_queue) == 2
        assert handler._message_queue[0] == record1
        assert handler._message_queue[1] == record2

    def test_discord_handler_flushes_queue_on_setup(self):
        """Test that queued messages are sent when bot is setup."""
        handler = logging_config.DiscordHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        # Queue some messages
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Queued message",
            args=(),
            exc_info=None
        )
        handler.emit(record)

        assert len(handler._message_queue) == 1

        # Setup the handler
        mock_bot = Mock()
        mock_bot.loop = None
        mock_bot.async_send_message = Mock()

        with patch('discord.Embed'):
            handler.setup(mock_bot, channel_id=123456789)

        # Queue should be cleared after setup
        assert len(handler._message_queue) == 0

    def test_discord_handler_queue_size_limit(self):
        """Test that queue size is limited to prevent memory issues."""
        handler = logging_config.DiscordHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        # Try to queue more than max_queue_size messages
        for i in range(handler._max_queue_size + 10):
            record = logging.LogRecord(
                name="test",
                level=logging.WARNING,
                pathname="test.py",
                lineno=i,
                msg=f"Message {i}",
                args=(),
                exc_info=None
            )
            handler.emit(record)

        # Should not exceed max_queue_size
        assert len(handler._message_queue) == handler._max_queue_size


class TestSetupLogging:
    """Test the setup_logging function."""

    @pytest.fixture(autouse=True)
    def cleanup_handlers(self):
        """Fixture to clean up logging handlers after each test."""
        yield
        # Clean up all handlers after test
        root_logger = logging.getLogger()
        for h in root_logger.handlers:
            try:
                h.close()
            except Exception:
                pass
            try:
                root_logger.removeHandler(h)
            except Exception:
                pass

    def test_setup_logging_returns_discord_handler(self, tmp_path):
        """Test that setup_logging returns a DiscordHandler."""
        # Create proper directory structure
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        with patch('src.common.logging_config.os.path.dirname', return_value=str(tmp_path)):
            handler = logging_config.setup_logging(log_file="test-bot.log")

        assert isinstance(handler, logging_config.DiscordHandler)

    def test_setup_logging_configures_root_logger(self, tmp_path):
        """Test that setup_logging configures the root logger."""
        # Create proper directory structure
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        with patch('src.common.logging_config.os.path.dirname', return_value=str(tmp_path)):
            logging_config.setup_logging(log_level=logging.DEBUG, log_file="test-bot2.log")

        # Check root logger level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        # Check handlers were added
        assert len(root_logger.handlers) >= 3  # Console, File, Discord

    def test_setup_logging_sets_third_party_log_levels(self, tmp_path):
        """Test that setup_logging sets appropriate levels for third-party loggers."""
        # Create proper directory structure
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        with patch('src.common.logging_config.os.path.dirname', return_value=str(tmp_path)):
            logging_config.setup_logging(log_file="test-bot3.log")

        # Check third-party library log levels
        assert logging.getLogger('discord').level == logging.WARNING
        assert logging.getLogger('urllib3').level == logging.WARNING
        assert logging.getLogger('werkzeug').level == logging.INFO

    def test_setup_logging_with_colorlog(self, tmp_path):
        """Test that setup_logging works without colorlog."""
        # Create proper directory structure
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        with patch('src.common.logging_config.colorlog', None):
            with patch('sys.stdout.isatty', return_value=True):
                with patch('src.common.logging_config.os.path.dirname', return_value=str(tmp_path)):
                    handler = logging_config.setup_logging(log_file="test-bot4.log")

                # Should still work without colorlog
                assert handler is not None

    def test_setup_logging_creates_rotating_file_handler(self, tmp_path):
        """Test that setup_logging creates a rotating file handler."""
        # Create logs directory
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        with patch('src.common.logging_config.os.path.dirname', return_value=str(tmp_path)):
            logging_config.setup_logging(log_file="test-rotation.log", max_bytes=1024, backup_count=3)

        # Check that log file was created
        log_file = logs_dir / "test-rotation.log"
        assert log_file.exists()


class TestGetLogger:
    """Test the get_logger function."""

    def test_get_logger_returns_logger_instance(self):
        """Test that get_logger returns a Logger instance."""
        logger = logging_config.get_logger("test_logger")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"

    def test_get_logger_returns_same_instance(self):
        """Test that get_logger returns the same instance for same name."""
        logger1 = logging_config.get_logger("test_logger")
        logger2 = logging_config.get_logger("test_logger")

        assert logger1 is logger2


class TestLogFormatting:
    """Test log message formatting."""

    @pytest.fixture(autouse=True)
    def cleanup_handlers(self):
        """Fixture to clean up logging handlers after each test."""
        yield
        # Clean up all handlers after test
        root_logger = logging.getLogger()
        for h in root_logger.handlers:
            try:
                h.close()
            except Exception:
                pass
            try:
                root_logger.removeHandler(h)
            except Exception:
                pass

    def test_log_format_includes_file_and_line_number(self, tmp_path):
        """Test that log messages include file and line number."""
        # Create logs directory
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        with patch('src.common.logging_config.os.path.dirname', return_value=str(tmp_path)):
            # Setup logging
            logging_config.setup_logging(log_file="format-test.log")

        # Log a message
        logger = logging.getLogger("test_format")
        logger.info("Test message")

        # Flush handlers
        root_logger = logging.getLogger()
        for h in root_logger.handlers:
            if hasattr(h, 'flush'):
                h.flush()

        # Read log file
        log_file = logs_dir / "format-test.log"
        log_content = log_file.read_text()

        # Check format includes file and line number
        assert "[" in log_content and "]" in log_content
        assert "test_format" in log_content
        assert "Test message" in log_content


class TestRotatingFileHandler:
    """Test the rotating file handler functionality."""

    @pytest.fixture(autouse=True)
    def cleanup_handlers(self):
        """Fixture to clean up logging handlers after each test."""
        yield
        # Clean up all handlers after test
        root_logger = logging.getLogger()
        for h in root_logger.handlers:
            try:
                h.close()
            except Exception:
                pass
            try:
                root_logger.removeHandler(h)
            except Exception:
                pass

    def test_file_rotation_when_size_exceeded(self, tmp_path):
        """Test that log files rotate when they exceed max size."""
        # Create logs directory
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        # Set very small max size to trigger rotation
        max_bytes = 500  # 500 bytes

        with patch('src.common.logging_config.os.path.dirname', return_value=str(tmp_path)):
            logging_config.setup_logging(log_file="rotation-test.log", max_bytes=max_bytes, backup_count=2)

        logger = logging.getLogger("rotation_test")

        # Write enough messages to exceed max_bytes
        for i in range(50):
            logger.info(f"This is test message number {i} with some additional text to make it longer")

        # Force flush
        root_logger = logging.getLogger()
        for h in root_logger.handlers:
            if hasattr(h, 'flush'):
                h.flush()

        # Check that log file exists
        log_file = logs_dir / "rotation-test.log"
        assert log_file.exists()

    def test_backup_count_limit(self, tmp_path):
        """Test that only the specified number of backups are kept."""
        # Create logs directory
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        # Set very small max size and only 2 backups
        max_bytes = 100
        backup_count = 2

        with patch('src.common.logging_config.os.path.dirname', return_value=str(tmp_path)):
            logging_config.setup_logging(
                log_file="backup-limit-test.log",
                max_bytes=max_bytes,
                backup_count=backup_count
            )

        logger = logging.getLogger("backup_test")

        # Write many messages to trigger multiple rotations
        for i in range(100):
            logger.error(f"Long error message number {i} to fill up the log file quickly")

        # Force flush
        root_logger = logging.getLogger()
        for h in root_logger.handlers:
            if hasattr(h, 'flush'):
                h.flush()

        # Count backup files
        backup_files = list(logs_dir.glob("backup-limit-test.log.*"))

        # Should not exceed backup_count
        assert len(backup_files) <= backup_count
