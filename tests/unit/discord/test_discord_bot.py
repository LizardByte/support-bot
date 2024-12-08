# standard imports
import asyncio
import os

# lib imports
import discord
import pytest

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


@pytest.mark.parametrize("message, embed", [
    (None, None),
    (f"This is a test message from {os.getenv('CI_EVENT_ID', 'local')}.", None),
    (None, discord.Embed(
        title="Test Embed 1",
        description="This is a test embed from the unit tests.",
        color=0x00ff00,
    )),
    (None, discord.Embed(
        title="Test Embed 2",
        description=f"{'a' * 4097}",  # ensure embed description is larger than 4096 characters
        color=0xff0000,
    )),
    (None, discord.Embed(
        title="Test Embed 3",
        description=f"{'a' * 4096}",
        color=0xff0000,
        footer=discord.EmbedFooter(
            text=f"{'b' * 2000}"  # ensure embed total size is larger than 6000 characters
        ),
    )),
])
def test_send_message(discord_bot, message, embed):
    channel_id = int(os.environ['DISCORD_GITHUB_STATUS_CHANNEL_ID'])
    msg = discord_bot.send_message(channel_id=channel_id, message=message, embed=embed)

    if not message and not embed:
        assert msg is None
        return

    if message:
        assert msg.content == message
    else:
        assert msg.content == ''

    assert msg.channel.id == channel_id
    assert msg.author.id == 939171917578002502
    assert msg.author.name == common.bot_name

    avatar_future = asyncio.run_coroutine_threadsafe(msg.author.avatar.read(), discord_bot.loop)
    assert avatar_future.result() == common.get_avatar_bytes()

    assert msg.author.display_name == common.bot_name
    assert msg.author.discriminator == "7085"
    assert msg.author.bot is True
    assert msg.author.system is False

    if embed:
        assert msg.embeds[0].title == embed.title
        assert msg.embeds[0].description == embed.description[:4093] + "..." if len(
            embed.description) > 4096 or len(embed) > 6000 else embed.description
        assert msg.embeds[0].color == embed.color
        if embed.footer:
            assert msg.embeds[0].footer.text == embed.footer.text
