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
    with bot.db as db:
        users_table = db.table('discord_users')
        discord_users = users_table.all()

    # Return early if there are no users to process
    if not discord_users:
        return False

    # Get the GitHub sponsors
    github_sponsors = sponsors.get_github_sponsors()

    # Process each user
    for user_data in discord_users:
        user_id = user_data.get('discord_id')
        if not user_id:
            continue

        # Get the currently revocable roles, to ensure we don't remove roles that were added by another integration
        # i.e.; any role that was added by our bot is safe to remove
        revocable_roles = user_data.get('roles', []).copy()

        # Check if the user is a GitHub sponsor
        for edge in github_sponsors['data']['organization']['sponsorshipsAsMaintainer']['edges']:
            sponsor = edge['node']['sponsorEntity']
            if sponsor['login'] == user_data.get('github_username'):
                # User is a sponsor
                user_data['github_sponsor'] = True

                monthly_amount = edge['node'].get('tier', {}).get('monthlyPriceInDollars', 0)

                for tier, amount in sponsors.tier_map.items():
                    if monthly_amount >= amount:
                        user_data['roles'] = [tier, 'supporters']
                        break
                else:
                    user_data['roles'] = []

                break
        else:
            # User is not a sponsor
            user_data['github_sponsor'] = False
            user_data['roles'] = []

        # Add GitHub user role if applicable
        if user_data.get('github_username'):
            user_data['roles'].append('github-user')

        # Update the discord user roles
        for g in bot.guilds:
            roles = g.roles

            role_map = {
                'github-user': discord.utils.get(roles, name='github-user'),
                'supporters': discord.utils.get(roles, name='supporters'),
                't1-sponsors': discord.utils.get(roles, name='t1-sponsors'),
                't2-sponsors': discord.utils.get(roles, name='t2-sponsors'),
                't3-sponsors': discord.utils.get(roles, name='t3-sponsors'),
                't4-sponsors': discord.utils.get(roles, name='t4-sponsors'),
            }

            user_roles = user_data['roles']

            for user_role, role in role_map.items():
                member = g.get_member(int(user_id))
                role = role_map.get(user_role, None)
                if not member or not role:
                    continue

                if user_role in user_roles:
                    if not test_mode:
                        await member.add_roles(role)
                    else:
                        # using a standard await fails inside unit tests, although it works normally
                        # RuntimeError: Timeout context manager should be used inside a task
                        add_future = asyncio.run_coroutine_threadsafe(member.add_roles(role), bot.loop)
                        add_future.result()
                elif user_role in revocable_roles:
                    if not test_mode:
                        await member.remove_roles(role)
                    else:
                        # using a standard await fails inside unit tests, although it works normally
                        # RuntimeError: Timeout context manager should be used inside a task
                        remove_future = asyncio.run_coroutine_threadsafe(member.remove_roles(role), bot.loop)
                        remove_future.result()

        # Update the user in the database
        with bot.db as db:
            users_table = db.table('discord_users')
            users_table.update(user_data, doc_ids=[user_data.get('doc_id')])

    return True
