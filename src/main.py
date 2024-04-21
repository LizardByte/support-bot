# standard imports
import os
import time

# development imports
from dotenv import load_dotenv
load_dotenv(override=False)  # environment secrets take priority over .env file

# local imports
if True:  # hack for flake8
    import discord_bot
    import keep_alive
    import reddit_bot


def main():
    # to run in replit
    try:
        os.environ['REPL_SLUG']
    except KeyError:
        pass  # not running in replit
    else:
        keep_alive.keep_alive()  # Start the web server

    discord_bot.start()  # Start the discord bot
    reddit_bot.start()  # Start the reddit bot

    try:
        while discord_bot.bot_thread.is_alive() or reddit_bot.bot_thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Keyboard Interrupt Detected")
        discord_bot.stop()  # Stop the discord bot
        reddit_bot.stop()


if __name__ == '__main__':
    main()
