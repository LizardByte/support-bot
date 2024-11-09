# standard imports
import os
import time

# lib imports
import dotenv
import pytest

# local imports
from src.common import globals

dotenv.load_dotenv(override=False)  # environment secrets take priority over .env file

# import after env loaded
from src.discord import bot as d_bot  # noqa: E402


@pytest.fixture(scope='session')
def discord_bot():
    bot = d_bot.Bot()
    bot.start_threaded()
    globals.DISCORD_BOT = bot

    while not bot.is_ready():  # Wait until the bot is ready
        time.sleep(1)

    yield bot

    bot.stop()
    globals.DISCORD_BOT = None


@pytest.fixture(scope='function')
def no_github_token():
    og_token = os.getenv('GITHUB_TOKEN')
    del os.environ['GITHUB_TOKEN']
    yield

    os.environ['GITHUB_TOKEN'] = og_token
