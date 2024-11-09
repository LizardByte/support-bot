# standard imports
import time

# development imports
from dotenv import load_dotenv
load_dotenv(override=False)  # environment secrets take priority over .env file

# local imports, import after env loaded
from src.common import globals  # noqa: E402
from src.discord import bot as d_bot  # noqa: E402
from src.common import webapp  # noqa: E402
from src.reddit import bot as r_bot  # noqa: E402


def main():
    webapp.start()  # Start the web server

    globals.DISCORD_BOT = d_bot.Bot()
    globals.DISCORD_BOT.start_threaded()  # Start the discord bot

    globals.REDDIT_BOT = r_bot.Bot()
    globals.REDDIT_BOT.start_threaded()  # Start the reddit bot

    try:
        while globals.DISCORD_BOT.bot_thread.is_alive() or globals.REDDIT_BOT.bot_thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Keyboard Interrupt Detected")
        globals.DISCORD_BOT.stop()
        globals.REDDIT_BOT.stop()


if __name__ == '__main__':  # pragma: no cover
    main()
