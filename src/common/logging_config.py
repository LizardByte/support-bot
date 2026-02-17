"""
Logging configuration module for the support bot.

This module provides a centralized logging configuration with multiple handlers:
- Console output with color support
- Rotating file handler (rotates when file reaches max size, keeps 5 files)
- Discord channel handler for critical logs
"""

# standard imports
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from typing import Optional

# lib imports
try:
    import colorlog
except ImportError:
    colorlog = None


class DiscordHandler(logging.Handler):
    """
    Custom logging handler that sends log messages to a Discord channel.

    Messages logged before the bot is ready are queued and sent once the bot is initialized.
    """

    def __init__(self, level=logging.WARNING):
        super().__init__(level)
        self.bot = None
        self.channel_id = None
        self._setup_complete = False
        self._message_queue = []  # Queue for messages before bot is ready
        self._max_queue_size = 50  # Limit queue size to prevent memory issues
        self._pending_tasks = set()  # Track active tasks to prevent garbage collection

    def setup(self, bot, channel_id: Optional[int] = None):
        """
        Setup the Discord handler with a bot instance and channel ID.

        After setup, any queued messages will be sent to Discord.

        Parameters
        ----------
        bot : discord.Bot or Bot
            The Discord bot instance.
        channel_id : int, optional
            The Discord channel ID to send logs to. If not provided, will use environment variable.
        """
        self.bot = bot
        self.channel_id = channel_id or os.getenv("DISCORD_LOG_CHANNEL_ID")
        if self.channel_id:
            self.channel_id = int(self.channel_id)
            self._setup_complete = True

            # Send any queued messages
            self._flush_queue()

    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to Discord.

        If the bot is not yet setup, the message is queued and will be sent once setup is complete.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to emit.
        """
        # If not setup yet, queue the message
        if not self._setup_complete or not self.channel_id:
            if len(self._message_queue) < self._max_queue_size:
                self._message_queue.append(record)
            return

        try:
            self._send_to_discord(record)
        except Exception:
            self.handleError(record)

    def _send_to_discord(self, record: logging.LogRecord):
        """
        Send a log record to Discord channel.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to send.
        """
        msg = self.format(record)

        # Create embed based on log level
        import discord
        import asyncio
        from datetime import datetime, UTC

        # Define colors here to avoid import issues
        color_map = {
            logging.DEBUG: 0x0000FF,  # Blue
            logging.INFO: 0x00FF00,  # Green
            logging.WARNING: 0xFFFF00,  # Yellow
            logging.ERROR: 0xFFA500,  # Orange
            logging.CRITICAL: 0xFF0000,  # Red
        }

        embed = discord.Embed(
            title=f"{record.levelname}",
            description=f"```\n{msg}\n```",
            color=color_map.get(record.levelno, 0x808080),
            timestamp=datetime.fromtimestamp(record.created, tz=UTC)  # Discord auto-formats as "X minutes ago"
        )

        # Add fields with better formatting
        embed.add_field(name="Logger", value=record.name, inline=True)
        # Format module field as "filename.py:lineno"
        module_info = f"{record.filename}:{record.lineno}"
        embed.add_field(name="Module", value=module_info, inline=True)
        embed.add_field(name="Function", value=record.funcName, inline=True)

        # Send message to Discord asynchronously without blocking
        # Use asyncio.create_task if we're in an event loop, otherwise use run_coroutine_threadsafe
        if self.bot and hasattr(self.bot, 'loop'):
            try:
                # Try to get the running loop
                loop = asyncio.get_running_loop()
                # If we're in the bot's event loop, schedule the task without waiting
                if loop == self.bot.loop:
                    # Create a task but don't wait for it
                    # Store the task to prevent garbage collection
                    task = asyncio.create_task(self.bot.async_send_message(
                        channel_id=self.channel_id,
                        embed=embed,
                    ))
                    self._pending_tasks.add(task)
                    # Remove task from set when completed to prevent memory leak
                    task.add_done_callback(self._pending_tasks.discard)
                else:
                    # We're in a different thread, use run_coroutine_threadsafe but don't wait
                    future = asyncio.run_coroutine_threadsafe(
                        self.bot.async_send_message(
                            channel_id=self.channel_id,
                            embed=embed,
                        ),
                        self.bot.loop
                    )
                    # Store future reference to prevent garbage collection
                    self._pending_tasks.add(future)
                    # Remove future from set when completed
                    future.add_done_callback(self._pending_tasks.discard)
            except RuntimeError:
                # No event loop running in this thread, use run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(
                    self.bot.async_send_message(
                        channel_id=self.channel_id,
                        embed=embed,
                    ),
                    self.bot.loop
                )
                # Store future reference to prevent garbage collection
                self._pending_tasks.add(future)
                # Remove future from set when completed
                future.add_done_callback(self._pending_tasks.discard)

    def _flush_queue(self):
        """
        Flush any queued messages to Discord.

        Called automatically when the bot is setup.
        """
        if not self._message_queue:
            return

        # Send all queued messages
        queued_count = len(self._message_queue)
        for record in self._message_queue:
            try:
                self._send_to_discord(record)
            except Exception:
                # Silently fail for queued messages to avoid spam
                pass

        # Clear the queue
        self._message_queue.clear()

        # Log that we flushed queued messages (but don't send this to Discord to avoid recursion)
        import logging
        logger = logging.getLogger(__name__)
        # Temporarily remove this handler to avoid recursion
        root_logger = logging.getLogger()
        if self in root_logger.handlers:
            root_logger.removeHandler(self)
            logger.info(f"Flushed {queued_count} queued log messages to Discord")
            root_logger.addHandler(self)


def setup_logging(
        log_level: int = logging.INFO,
        log_file: str = "support-bot.log",
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
) -> DiscordHandler:
    """
    Setup logging configuration with multiple handlers.

    Parameters
    ----------
    log_level : int, optional
        The logging level (default: logging.INFO).
    log_file : str, optional
        The log file name (default: "support-bot.log").
    max_bytes : int, optional
        Maximum size of each log file before rotation (default: 10 MB).
    backup_count : int, optional
        Number of backup log files to keep (default: 5).

    Returns
    -------
    DiscordHandler
        The Discord handler instance that needs to be configured later.
    """
    # Compute data_dir locally to avoid circular imports
    # Get the application directory
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(app_dir, "data")

    # Create logs directory
    logs_dir = os.path.join(data_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Define log format with file, module, and line number
    log_format = "%(asctime)s - %(name)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 1. Console Handler with color support
    if colorlog and sys.stdout.isatty():
        # Use colorlog if available and stdout is a TTY
        console_handler = colorlog.StreamHandler()
        console_formatter = colorlog.ColoredFormatter(
            fmt="%(log_color)s%(asctime)s - %(name)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s",
            datefmt=date_format,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            },
        )
        console_handler.setFormatter(console_formatter)
    else:
        # Fallback to standard console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(log_format, datefmt=date_format)
        console_handler.setFormatter(console_formatter)

    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handler (rotates automatically when file reaches max_bytes)
    log_file_path = os.path.join(logs_dir, log_file)
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)

    # 3. Discord Handler (will be configured later)
    discord_handler = DiscordHandler(level=logging.WARNING)  # Only send WARNING and above to Discord
    discord_formatter = logging.Formatter("%(message)s")
    discord_handler.setFormatter(discord_formatter)
    root_logger.addHandler(discord_handler)

    # Set logging levels for noisy libraries
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    logging.getLogger('discord.client').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('prawcore').setLevel(logging.WARNING)
    logging.getLogger('praw').setLevel(logging.WARNING)

    root_logger.info("Logging system initialized")
    root_logger.info(f"Log file: {log_file_path}")
    root_logger.info(f"Console color support: {'enabled' if colorlog and sys.stdout.isatty() else 'disabled'}")

    return discord_handler


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Parameters
    ----------
    name : str
        The name of the logger.

    Returns
    -------
    logging.Logger
        The logger instance.
    """
    return logging.getLogger(name)
