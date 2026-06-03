# standard imports
from types import SimpleNamespace

# lib imports
import pytest

# local imports
from src.discord_bot.cogs.base_commands import BaseCommandsCog


def command(
        *,
        description='Command description',
        options=None,
        permissions=None,
        docstring='Doc fallback.\n\nParameters\n----------\nctx : object',
):
    def callback():
        return None

    callback.__doc__ = docstring
    return SimpleNamespace(
        name='example',
        description=description,
        options=options or [],
        default_member_permissions=permissions,
        callback=callback,
    )


def context(**permissions):
    return SimpleNamespace(
        author=SimpleNamespace(
            guild_permissions=SimpleNamespace(**permissions),
        ),
    )


@pytest.mark.asyncio
async def test_get_command_help_without_permission():
    cmd = command(permissions=[('manage_guild', True)])

    assert await BaseCommandsCog.get_command_help(ctx=context(manage_guild=False), cmd=cmd) == ''


@pytest.mark.asyncio
async def test_get_command_help_with_group_description_and_options():
    cmd = command(
        options=[
            SimpleNamespace(name='required', description='Required option', required=True),
            SimpleNamespace(name='optional', description='Optional option', required=False),
        ],
        permissions=[('manage_guild', True)],
    )

    description = await BaseCommandsCog.get_command_help(
        ctx=context(manage_guild=True),
        cmd=cmd,
        group_name='group',
    )

    assert description == (
        '### `/group example`\n'
        'Command description\n'
        '\n'
        '**Options:**\n'
        '`required`: Required option (Required)\n'
        '`optional`: Optional option (Optional)\n'
        '\n'
    )


@pytest.mark.asyncio
async def test_get_command_help_uses_docstring_fallback():
    cmd = command(description='')

    description = await BaseCommandsCog.get_command_help(ctx=context(), cmd=cmd)

    assert description == '### `/example`\nDoc fallback.\n\n'


def test_command_help_helpers():
    cmd = command(description='', options=[])

    assert BaseCommandsCog.has_command_permissions(ctx=context(), permissions=None) is True
    assert BaseCommandsCog.command_help_title(cmd=cmd) == '### `/example`\n'
    assert BaseCommandsCog.command_options_help(options=[]) == ''
