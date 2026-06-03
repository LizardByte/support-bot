# standard imports
from datetime import datetime, timedelta, timezone, UTC
import os
from types import SimpleNamespace

# lib imports
import pytest

# local imports
from src.discord_bot import tasks


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
@pytest.mark.parametrize("skip", [True, False])
async def test_role_update_task(discord_bot, discord_db_users, mocker, skip):
    """
    WHEN the role update task is called
    THEN check that the task runs without error
    """
    # Patch datetime.datetime at the location where it's imported in `tasks`
    mock_datetime = mocker.patch('src.discord_bot.tasks.datetime', autospec=True)
    mock_datetime.now.return_value = datetime(2023, 1, 1, 0, 1 if skip else 0, 0, tzinfo=timezone.utc)

    # Run the task
    result = await tasks.role_update_task(bot=discord_bot, test_mode=True)

    assert result is not skip

    # Verify that datetime.now() was called
    mock_datetime.now.assert_called_once()


def github_sponsors_payload(monthly_amount=25, login='test_user'):
    return {
        'data': {
            'organization': {
                'sponsorshipsAsMaintainer': {
                    'edges': [
                        {
                            'node': {
                                'sponsorEntity': {'login': login},
                                'tier': {'monthlyPriceInDollars': monthly_amount},
                            },
                        },
                    ],
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_role_update_task_no_users(mocker):
    mock_datetime = mocker.patch('src.discord_bot.tasks.datetime', autospec=True)
    mock_datetime.now.return_value = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mocker.patch('src.discord_bot.tasks._get_discord_users', return_value=[])

    result = await tasks.role_update_task(bot=mocker.Mock(), test_mode=True)

    assert result is False


def test_update_sponsor_role_data_for_sponsor_and_non_sponsor():
    sponsor_user = {'github_username': 'test_user', 'roles': ['supporters']}
    tasks._update_sponsor_role_data(
        user_data=sponsor_user,
        github_sponsors=github_sponsors_payload(monthly_amount=25),
    )

    assert sponsor_user['github_sponsor'] is True
    assert sponsor_user['roles'] == ['t4-sponsors', 'supporters', 'github-user']

    non_sponsor = {'github_username': 'other_user', 'roles': ['supporters']}
    tasks._update_sponsor_role_data(
        user_data=non_sponsor,
        github_sponsors=github_sponsors_payload(monthly_amount=1),
    )

    assert non_sponsor['github_sponsor'] is False
    assert non_sponsor['roles'] == ['github-user']


def test_find_sponsor_edge_and_sponsor_roles():
    payload = github_sponsors_payload(monthly_amount=0)

    assert tasks._find_sponsor_edge(payload, 'test_user') is payload[
        'data']['organization']['sponsorshipsAsMaintainer']['edges'][0]
    assert tasks._find_sponsor_edge(payload, 'missing') is None
    assert tasks._sponsor_roles(payload['data']['organization']['sponsorshipsAsMaintainer']['edges'][0]) == []


def test_role_map(mocker):
    roles = [SimpleNamespace(name='github-user'), SimpleNamespace(name='supporters')]
    guild = SimpleNamespace(roles=roles)

    role_map = tasks._role_map(guild=guild)

    assert role_map['github-user'] is roles[0]
    assert role_map['supporters'] is roles[1]
    assert role_map['t1-sponsors'] is None


@pytest.mark.asyncio
async def test_sync_guild_roles_skips_missing_member_or_role(mocker):
    bot = SimpleNamespace(loop=mocker.Mock())
    guild = SimpleNamespace(
        get_member=mocker.Mock(return_value=None),
        roles=[],
    )

    await tasks._sync_guild_roles(
        bot=bot,
        guild=guild,
        user_id=123,
        user_roles=['github-user'],
        revocable_roles=[],
        test_mode=False,
    )

    guild.get_member.assert_called_once_with(123)

    member = SimpleNamespace(add_roles=mocker.AsyncMock(), remove_roles=mocker.AsyncMock())
    role = SimpleNamespace(name='github-user')
    guild.get_member.return_value = member
    guild.roles = [role]

    await tasks._sync_guild_roles(
        bot=bot,
        guild=guild,
        user_id=123,
        user_roles=[],
        revocable_roles=[],
        test_mode=False,
    )

    member.add_roles.assert_not_called()
    member.remove_roles.assert_not_called()


@pytest.mark.asyncio
async def test_sync_member_role_adds_and_removes(mocker):
    bot = SimpleNamespace(loop=mocker.Mock())
    role = SimpleNamespace(name='github-user')
    member = SimpleNamespace(add_roles=mocker.AsyncMock(), remove_roles=mocker.AsyncMock())

    await tasks._sync_member_role(
        bot=bot,
        member=member,
        role=role,
        should_have_role=True,
        can_revoke_role=False,
        test_mode=False,
    )
    await tasks._sync_member_role(
        bot=bot,
        member=member,
        role=role,
        should_have_role=False,
        can_revoke_role=True,
        test_mode=False,
    )

    member.add_roles.assert_awaited_once_with(role)
    member.remove_roles.assert_awaited_once_with(role)


@pytest.mark.asyncio
async def test_run_role_action_test_mode(mocker):
    role = SimpleNamespace(name='github-user')
    action = mocker.Mock(return_value='coroutine')
    future = mocker.Mock()
    run_coroutine_threadsafe = mocker.patch(
        'src.discord_bot.tasks.asyncio.run_coroutine_threadsafe',
        return_value=future,
    )
    bot = SimpleNamespace(loop='loop')

    await tasks._run_role_action(bot=bot, test_mode=True, action=action, role=role)

    action.assert_called_once_with(role)
    run_coroutine_threadsafe.assert_called_once_with('coroutine', 'loop')
    future.result.assert_called_once()


@pytest.mark.asyncio
async def test_process_discord_user_roles(mocker):
    role = SimpleNamespace(name='github-user')
    member = SimpleNamespace(add_roles=mocker.AsyncMock(), remove_roles=mocker.AsyncMock())
    guild = SimpleNamespace(
        get_member=mocker.Mock(return_value=member),
        roles=[role],
    )
    users_table = SimpleNamespace(update=mocker.Mock())
    db_context = mocker.MagicMock()
    db_context.__enter__.return_value.table.return_value = users_table
    bot = SimpleNamespace(db=db_context, guilds=[guild], loop=mocker.Mock())
    user_data = {
        'discord_id': '123',
        'github_username': 'test_user',
        'roles': [],
        'doc_id': 5,
    }

    await tasks._process_discord_user_roles(
        bot=bot,
        user_data=user_data,
        github_sponsors=github_sponsors_payload(monthly_amount=1),
        test_mode=False,
    )

    member.add_roles.assert_awaited_once_with(role)
    users_table.update.assert_called_once_with(user_data, doc_ids=[5])


@pytest.mark.asyncio
async def test_process_discord_user_roles_skips_missing_user_id(mocker):
    bot = SimpleNamespace(guilds=[], db=mocker.Mock())
    user_data = {'github_username': 'test_user'}

    await tasks._process_discord_user_roles(
        bot=bot,
        user_data=user_data,
        github_sponsors=github_sponsors_payload(),
        test_mode=False,
    )

    bot.db.assert_not_called()
