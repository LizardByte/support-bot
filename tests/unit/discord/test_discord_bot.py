# standard imports
import asyncio
import os

# local imports
from src.common import common


def test_bot_on_ready(discord_bot):
    assert discord_bot is not None
    assert discord_bot.guilds
    assert discord_bot.guilds[0].name == "ReenigneArcher's test server"
    assert discord_bot.user.id == 939171917578002502
    assert discord_bot.user.name == common.bot_name
    assert discord_bot.user.avatar

    # compare the bot avatar to our intended avatar
    future = asyncio.run_coroutine_threadsafe(discord_bot.user.avatar.read(), discord_bot.loop)
    assert future.result() == common.get_avatar_bytes()


def test_send_message(discord_bot):
    channel_id = int(os.environ['DISCORD_REDDIT_CHANNEL_ID'])
    message = f"This is a test message from {os.getenv('CI_EVENT_ID', 'local')}."
    embeds = []
    msg = discord_bot.send_message(channel_id=channel_id, message=message, embeds=embeds)
    assert msg.content == message
    assert msg.channel.id == channel_id
    assert msg.author.id == 939171917578002502
    assert msg.author.name == common.bot_name

    avatar_future = asyncio.run_coroutine_threadsafe(msg.author.avatar.read(), discord_bot.loop)
    assert avatar_future.result() == common.get_avatar_bytes()

    assert msg.author.display_name == common.bot_name
    assert msg.author.discriminator == "7085"
    assert msg.author.bot is True
    assert msg.author.system is False
