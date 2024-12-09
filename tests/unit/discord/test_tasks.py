# standard imports
from datetime import datetime, timedelta, timezone, UTC
import os

# lib imports
import pytest

# local imports
from src.discord import tasks


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
@pytest.mark.parametrize("db_start, expected_keys", [
    (
        {
            '1': {
                'expires_at': datetime.now(UTC),
            },
            '2': {
                'expires_at': datetime.now(UTC) - timedelta(minutes=1)
            },
            '3': {
                'expires_at': datetime.now(UTC) - timedelta(minutes=2)
            },
            '4': {
                'expires_at': datetime.now(UTC) - timedelta(minutes=3)
            },
            '5': {
                'expires_at': datetime.now(UTC) - timedelta(minutes=4)
            },
            '6': {
                'expires_at': datetime.now(UTC) - timedelta(minutes=5)
            },
            '7': {
                'expires_at': datetime.now(UTC) - timedelta(minutes=10)
            },
        },
        ['1', '2', '3', '4', '5']
    )
])
async def test_clean_ephemeral_cache(discord_bot, mocker, db_start, expected_keys):
    """
    GIVEN a database with ephemeral cache entries
    WHEN the clean_ephemeral_cache task is called
    THEN expired entries are removed from the database
    """
    # Mock the edit method of the response objects
    for entry in db_start.values():
        entry['response'] = mocker.Mock()
        entry['response'].edit = mocker.AsyncMock()

    # Mock the bot's ephemeral_db
    discord_bot.ephemeral_db = {
        'github_cache_context': db_start
    }

    # Run the clean_ephemeral_cache task
    await tasks.clean_ephemeral_cache(bot=discord_bot)

    # Assert the ephemeral_db is as expected
    for k, v in discord_bot.ephemeral_db['github_cache_context'].items():
        assert k in expected_keys, f"Key {k} should not be in the database"
        assert v['expires_at'] >= datetime.now(UTC) - timedelta(minutes=5), f"Key {k} should not have expired"


@pytest.mark.asyncio
@pytest.mark.parametrize("skip, set_daily_releases, set_daily_channel_id, expected", [
    (True, 'false', None, False),
    (False, 'false', None, False),
    (False, 'true', None, False),
    (False, 'true', os.environ['DISCORD_GITHUB_STATUS_CHANNEL_ID'], True),
], indirect=["set_daily_releases", "set_daily_channel_id"])
async def test_daily_task(discord_bot, mocker, skip, set_daily_releases, set_daily_channel_id, expected):
    """
    WHEN the daily task is called
    THEN check that the task runs without error
    """
    # Patch datetime.datetime at the location where it's imported in `tasks`
    mock_datetime = mocker.patch('src.discord.tasks.datetime', autospec=True)
    mock_datetime.now.return_value = datetime(2023, 1, 1, 1 if skip else 12, 0, 0, tzinfo=timezone.utc)

    # Run the daily task
    result = await tasks.daily_task(bot=discord_bot)

    assert result is expected

    # Verify that datetime.now() was called
    mock_datetime.now.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("skip", [True, False])
async def test_role_update_task(discord_bot, discord_db_users, mocker, skip):
    """
    WHEN the role update task is called
    THEN check that the task runs without error
    """
    # Patch datetime.datetime at the location where it's imported in `tasks`
    mock_datetime = mocker.patch('src.discord.tasks.datetime', autospec=True)
    mock_datetime.now.return_value = datetime(2023, 1, 1, 0, 1 if skip else 0, 0, tzinfo=timezone.utc)

    # Run the task
    result = await tasks.role_update_task(bot=discord_bot)

    assert result is not skip

    # Verify that datetime.now() was called
    mock_datetime.now.assert_called_once()
