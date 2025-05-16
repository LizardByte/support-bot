# standard imports
import asyncio
import os
import time

# lib imports
import dotenv
import pytest

# local imports
from src.common import globals

dotenv.load_dotenv(override=False)  # environment secrets take priority over .env file

# import after env loaded
from src.discord_bot import bot as d_bot  # noqa: E402


@pytest.fixture(scope='session')
def discord_bot():
    bot = d_bot.Bot()
    bot.start_threaded()
    globals.DISCORD_BOT = bot

    while not bot.is_ready():  # Wait until the bot is ready
        time.sleep(1)

    bot.role_update_task.stop()
    bot.daily_task.stop()
    bot.clean_ephemeral_cache.stop()

    yield bot

    bot.stop()
    globals.DISCORD_BOT = None


@pytest.fixture(scope='function')
def discord_db_users(discord_bot):
    with discord_bot.db as db:
        users_table = db.table('discord_users')
        users_table.insert({
            'user_id': 939171917578002502,
            'discord_username': 'test_user',
            'discord_global_name': 'Test User',
            'github_id': 123,
            'github_username': 'test_user',
            'roles': ['supporters']
        })

    discord_bot.oauth_states[939171917578002502] = 'valid_state'

    yield

    # Clean up test data
    with discord_bot.db as db:
        db.table('discord_users').truncate()
    discord_bot.oauth_states.clear()


@pytest.fixture(scope='function')
def no_github_token():
    og_token = os.getenv('GITHUB_TOKEN')
    del os.environ['GITHUB_TOKEN']
    yield

    os.environ['GITHUB_TOKEN'] = og_token


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop that isn't closed after each test.

    This is necessary for pytest-asyncio 0.26.0 and later, as it fails to closes the loop after each test.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    loop.close()
