# standard imports
from datetime import datetime, UTC
import logging
from types import SimpleNamespace

# lib imports
import pytest

# local imports
from src.discord_bot.cogs.autoban import AutoBanCog


@pytest.mark.asyncio
async def test_autoban_does_not_read_message_content(caplog, mocker, monkeypatch):
    monkeypatch.setenv('DISCORD_AUTOBAN_CHANNEL_ID', '123')
    guild = SimpleNamespace(
        ban=mocker.AsyncMock(),
        id=456,
        name='Test guild',
    )
    message = SimpleNamespace(
        author=SimpleNamespace(bot=False, id=789),
        channel=SimpleNamespace(id=123, name='restricted'),
        created_at=datetime(2026, 9, 13, tzinfo=UTC),
        guild=guild,
        id=101112,
    )

    with caplog.at_level(logging.WARNING):
        await AutoBanCog(bot=mocker.Mock()).on_message(message)

    guild.ban.assert_awaited_once_with(
        user=message.author,
        reason="Automatic ban: posted in restricted channel.",
        delete_message_seconds=604800,
    )
    assert "Message ID: 101112" in caplog.text
    assert "Message created at: 2026-09-13T00:00:00+00:00" in caplog.text
