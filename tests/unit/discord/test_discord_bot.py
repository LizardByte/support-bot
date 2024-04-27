# standard imports
import asyncio

# lib imports
import pytest
import pytest_asyncio

# local imports
from src import common
from src.discord import bot as discord_bot


@pytest_asyncio.fixture
async def bot():
    # event_loop fixture is deprecated
    _loop = asyncio.get_event_loop()

    bot = discord_bot.Bot(loop=_loop)
    future = asyncio.run_coroutine_threadsafe(bot.start(token=bot.token), _loop)
    await bot.wait_until_ready()  # Wait until the bot is ready
    yield bot
    bot.stop(future=future)

    # wait for the bot to finish
    counter = 0
    while not future.done() and counter < 30:
        await asyncio.sleep(1)
        counter += 1
    future.cancel()  # Cancel the bot when the tests are done


@pytest.mark.asyncio
async def test_bot_on_ready(bot):
    assert bot is not None
    assert bot.guilds
    assert bot.guilds[0].name == "ReenigneArcher's test server"
    assert bot.user.id == 939171917578002502
    assert bot.user.name == common.bot_name
    assert bot.user.avatar

    # compare the bot avatar to our intended avatar
    assert await bot.user.avatar.read() == common.get_avatar_bytes()
