# standard imports
import asyncio

# lib imports
import pytest

# local imports
from src.discord_bot.cogs.fun_commands import FunCommandsCog
from src.discord_bot.cogs.support_commands import SupportCommandsCog


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raise_for_status_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        self.raise_for_status_called = True

    async def json(self):
        await asyncio.sleep(0)
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *, url):
        self.url = url
        return self.response


def test_render_command_file(tmp_path):
    command_file = tmp_path / "help.md"
    command_file.write_text("# Heading\n\nBody text.\n", encoding="utf-8")

    rendered = SupportCommandsCog.render_command_file(str(command_file))

    assert "Heading" in rendered
    assert "Body text." in rendered


@pytest.mark.asyncio
async def test_get_random_quotes_uses_aiohttp(mocker):
    payload = [{'quote': 'Test quote', 'game': 'Test Game', 'character': 'Test Character'}]
    response = FakeResponse(payload=payload)
    session = FakeSession(response=response)
    client_session = mocker.patch('src.discord_bot.cogs.fun_commands.aiohttp.ClientSession', return_value=session)

    quotes = await FunCommandsCog(bot=object()).get_random_quotes()

    assert quotes == payload
    assert session.url == 'https://app.lizardbyte.dev/uno/random-quotes/games.json'
    assert response.raise_for_status_called is True
    client_session.assert_called_once_with()
