# standard imports
import asyncio
import copy
from datetime import datetime, UTC

# lib imports
import discord
from discord.ext import tasks

# local imports
from src.common import sponsors
from src.discord_bot.bot import Bot


@tasks.loop(seconds=30)
async def clean_ephemeral_cache(bot: Bot) -> bool:
    """
    Clean ephemeral messages in cache.

    This function runs on a schedule, every 30 seconds.
    Check the ephemeral database for expired messages and delete them.
    """
    for key, value in copy.deepcopy(bot.ephemeral_db.get('github_cache_context', {})).items():
        if value['expires_at'] < datetime.now(UTC):
            bot.update_cached_message(author_id=int(key), reason='timeout')

    return True


@tasks.loop(minutes=1.0)
async def role_update_task(bot: Bot, test_mode: bool = False) -> bool:
    """
    Run the role update task.

    This function runs on a schedule, every 1 minute.
    If the current time is not divisible by 10, return False. e.g. Run every 10 minutes.

    Parameters
    ----------
    bot : Bot
        The Discord bot instance.
    test_mode : bool, optional
        Whether to run the task in test mode, by default False. This simply affects how the roles are assigned.

    Returns
    -------
    bool
        True if the task ran successfully, False otherwise.
    """
    if datetime.now(UTC).minute not in list(range(0, 60, 10)):
        return False

    # Check each user in the database for their GitHub sponsor status
    discord_users = _get_discord_users(bot=bot)

    # Return early if there are no users to process
    if not discord_users:
        return False

    # Get the GitHub sponsors
    github_sponsors = sponsors.get_github_sponsors()

    # Process each user
    for user_data in discord_users:
        await _process_discord_user_roles(
            bot=bot,
            user_data=user_data,
            github_sponsors=github_sponsors,
            test_mode=test_mode,
        )

    return True


def _get_discord_users(bot: Bot) -> list[dict]:
    with bot.db as db:
        users_table = db.table('discord_users')
        return users_table.all()


async def _process_discord_user_roles(
        bot: Bot,
        user_data: dict,
        github_sponsors: dict,
        test_mode: bool,
):
    user_id = user_data.get('discord_id')
    if not user_id:
        return

    # Revocable roles were added by this bot and can be removed if no longer applicable.
    revocable_roles = user_data.get('roles', []).copy()
    _update_sponsor_role_data(user_data=user_data, github_sponsors=github_sponsors)

    for guild in bot.guilds:
        await _sync_guild_roles(
            bot=bot,
            guild=guild,
            user_id=int(user_id),
            user_roles=user_data['roles'],
            revocable_roles=revocable_roles,
            test_mode=test_mode,
        )

    _update_discord_user(bot=bot, user_data=user_data)


def _update_sponsor_role_data(user_data: dict, github_sponsors: dict):
    sponsor_edge = _find_sponsor_edge(
        github_sponsors=github_sponsors,
        github_username=user_data.get('github_username'),
    )

    if sponsor_edge:
        user_data['github_sponsor'] = True
        user_data['roles'] = _sponsor_roles(edge=sponsor_edge)
    else:
        user_data['github_sponsor'] = False
        user_data['roles'] = []

    # Add GitHub user role if applicable
    if user_data.get('github_username'):
        user_data['roles'].append('github-user')


def _find_sponsor_edge(github_sponsors: dict, github_username: str) -> dict | None:
    edges = github_sponsors['data']['organization']['sponsorshipsAsMaintainer']['edges']
    for edge in edges:
        sponsor = edge['node']['sponsorEntity']
        if sponsor['login'] == github_username:
            return edge

    return None


def _sponsor_roles(edge: dict) -> list[str]:
    monthly_amount = edge['node'].get('tier', {}).get('monthlyPriceInDollars', 0)

    for tier, amount in sponsors.tier_map.items():
        if monthly_amount >= amount:
            return [tier, 'supporters']

    return []


async def _sync_guild_roles(
        bot: Bot,
        guild: discord.Guild,
        user_id: int,
        user_roles: list[str],
        revocable_roles: list[str],
        test_mode: bool,
):
    member = guild.get_member(user_id)
    if not member:
        return

    for user_role, role in _role_map(guild=guild).items():
        if not role:
            continue

        await _sync_member_role(
            bot=bot,
            member=member,
            role=role,
            should_have_role=user_role in user_roles,
            can_revoke_role=user_role in revocable_roles,
            test_mode=test_mode,
        )


def _role_map(guild: discord.Guild) -> dict[str, discord.Role | None]:
    roles = guild.roles
    return {
        'github-user': discord.utils.get(roles, name='github-user'),
        'supporters': discord.utils.get(roles, name='supporters'),
        't1-sponsors': discord.utils.get(roles, name='t1-sponsors'),
        't2-sponsors': discord.utils.get(roles, name='t2-sponsors'),
        't3-sponsors': discord.utils.get(roles, name='t3-sponsors'),
        't4-sponsors': discord.utils.get(roles, name='t4-sponsors'),
    }


async def _sync_member_role(
        bot: Bot,
        member: discord.Member,
        role: discord.Role,
        should_have_role: bool,
        can_revoke_role: bool,
        test_mode: bool,
):
    if should_have_role:
        await _run_role_action(bot=bot, test_mode=test_mode, action=member.add_roles, role=role)
    elif can_revoke_role:
        await _run_role_action(bot=bot, test_mode=test_mode, action=member.remove_roles, role=role)


async def _run_role_action(bot: Bot, test_mode: bool, action, role: discord.Role):
    if not test_mode:
        await action(role)
        return

    # A standard await fails in unit tests: RuntimeError: Timeout context manager should be used inside a task.
    future = asyncio.run_coroutine_threadsafe(action(role), bot.loop)
    future.result()


def _update_discord_user(bot: Bot, user_data: dict):
    with bot.db as db:
        users_table = db.table('discord_users')
        users_table.update(user_data, doc_ids=[user_data.get('doc_id')])
