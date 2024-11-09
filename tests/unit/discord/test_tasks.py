# standard imports
from datetime import datetime, timezone
import os

# lib imports
import pytest

# local imports
from src.discord import tasks


@pytest.fixture(scope='function')
def discord_bot_with_no_tasks(discord_bot):
    """
    Create a discord bot with no tasks.
    """
    discord_bot.hourly_task.stop()
    discord_bot.daily_task.stop()
    yield discord_bot


def set_env_variable(env_var_name, request):
    og_value = os.environ.get(env_var_name)
    new_value = request.param
    if new_value is not None:
        os.environ[env_var_name] = new_value
    yield
    if og_value is not None:
        os.environ[env_var_name] = og_value
    elif env_var_name in os.environ:
        del os.environ[env_var_name]


@pytest.fixture(scope='function')
def set_daily_channel_id(request):
    yield from set_env_variable('DAILY_CHANNEL_ID', request)


@pytest.fixture(scope='function')
def set_daily_releases(request):
    yield from set_env_variable('DAILY_RELEASES', request)


@pytest.mark.asyncio
@pytest.mark.parametrize("skip, set_daily_releases, set_daily_channel_id, expected", [
    (True, 'false', None, False),
    (False, 'false', None, False),
    (False, 'true', None, False),
    (False, 'true', os.environ['DISCORD_GITHUB_STATUS_CHANNEL_ID'], True),
], indirect=["set_daily_releases", "set_daily_channel_id"])
async def test_daily_task(discord_bot_with_no_tasks, mocker, skip, set_daily_releases, set_daily_channel_id, expected):
    """
    WHEN the daily task is called
    THEN check that the task runs without error
    """
    # Patch datetime.datetime at the location where it's imported in `tasks`
    mock_datetime = mocker.patch('src.discord.tasks.datetime', autospec=True)
    mock_datetime.now.return_value = datetime(2023, 1, 1, 1 if skip else 12, 0, 0, tzinfo=timezone.utc)

    # Run the daily task
    result = await tasks.daily_task(bot=discord_bot_with_no_tasks)

    assert result is expected

    # Verify that datetime.now() was called
    mock_datetime.now.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("skip", [True, False])
async def test_hourly_task(discord_bot_with_no_tasks, mocker, skip):
    """
    WHEN the hourly task is called
    THEN check that the task runs without error
    """
    # Patch datetime.datetime at the location where it's imported in `tasks`
    mock_datetime = mocker.patch('src.discord.tasks.datetime', autospec=True)
    mock_datetime.now.return_value = datetime(2023, 1, 1, 0, 1 if skip else 0, 0, tzinfo=timezone.utc)

    # Run the hourly task
    result = await tasks.hourly_task(bot=discord_bot_with_no_tasks)

    assert result is not skip

    # Verify that datetime.now() was called
    mock_datetime.now.assert_called_once()
