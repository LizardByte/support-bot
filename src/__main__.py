# standard imports
import logging
import time

# development imports
from dotenv import load_dotenv
load_dotenv(override=False)  # environment secrets take priority over .env file

# local imports, import after env loaded
from src.common import globals  # noqa: E402
from src.common import logging_config  # noqa: E402
from src.discord_bot import bot as d_bot  # noqa: E402
from src.common import webapp  # noqa: E402
from src.reddit_bot import bot as r_bot  # noqa: E402

# Get logger for this module
logger = logging.getLogger(__name__)


def main():
    # Initialize logging system
    discord_handler = logging_config.setup_logging()

    webapp.start()  # Start the web server

    globals.DISCORD_BOT = d_bot.Bot()
    globals.DISCORD_BOT.start_threaded()  # Start the discord bot

    # Configure Discord handler after bot is initialized
    discord_handler.setup(globals.DISCORD_BOT)

    globals.REDDIT_BOT = r_bot.Bot()
    globals.REDDIT_BOT.start_threaded()  # Start the reddit bot

    try:
        while globals.DISCORD_BOT.bot_thread.is_alive() or globals.REDDIT_BOT.bot_thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Keyboard Interrupt Detected")
        globals.DISCORD_BOT.stop()
        globals.REDDIT_BOT.stop()


if __name__ == '__main__':  # pragma: no cover
    main()
