# standard imports
import asyncio
import copy
from datetime import datetime, UTC
import json
import os

# lib imports
import discord
from discord.ext import tasks
from igdb.wrapper import IGDBWrapper

# local imports
from src.common.common import avatar, bot_name, bot_url, colors
from src.common import sponsors
from src.discord_bot.bot import Bot
from src.discord_bot.helpers import igdb_authorization, month_dictionary


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


@tasks.loop(minutes=60.0)
async def daily_task(bot: Bot) -> bool:
    """
    Run daily task loop.

    This function runs on a schedule, every 60 minutes. Create an embed and thread for each game released
    on this day in history (according to IGDB), if enabled.

    Returns
    -------
    bool
        True if the task ran successfully, False otherwise.
    """
    date = datetime.now(UTC)
    if date.hour != int(os.getenv(key='DAILY_TASKS_UTC_HOUR', default=12)):
        return False

    daily_releases = True if os.getenv(key='DAILY_RELEASES', default='true').lower() == 'true' else False
    if not daily_releases:
        print("'DAILY_RELEASES' environment variable is disabled")
        return False

    try:
        channel_id = int(os.environ['DAILY_CHANNEL_ID'])
    except KeyError:
        print("'DAILY_CHANNEL_ID' not defined in environment variables.")
        return False

    igdb_auth = igdb_authorization(client_id=os.environ['IGDB_CLIENT_ID'],
                                   client_secret=os.environ['IGDB_CLIENT_SECRET'])
    wrapper = IGDBWrapper(client_id=os.environ['IGDB_CLIENT_ID'], auth_token=igdb_auth['access_token'])

    end_point = 'release_dates'
    fields = [
        'human',
        'game.name',
        'game.summary',
        'game.url',
        'game.genres.name',
        'game.rating',
        'game.cover.url',
        'game.artworks.url',
        'game.platforms.name',
        'game.platforms.url'
    ]

    where = f'human="{month_dictionary[date.month]} {date.day:02d}"*'
    limit = 500
    query = f'fields {", ".join(fields)}; where {where}; limit {limit};'

    byte_array = bytes(wrapper.api_request(endpoint=end_point, query=query))
    json_result = json.loads(byte_array)

    game_ids = []

    for game in json_result:
        try:
            game_id = game['game']['id']
        except KeyError:
            continue

        if game_id in game_ids:
            continue  # do not repeat the same game... even though it could be a different platform
        game_ids.append(game_id)

        try:
            embed = discord.Embed(
                title=game['game']['name'],
                url=game['game']['url'],
                description=game['game']['summary'][0:2000 - 1],
                color=colors['purple']
            )
        except KeyError:
            continue

        try:
            rating = round(game['game']['rating'] / 20, 1)
            embed.add_field(
                name='Average Rating',
                value=f'⭐{rating}',
                inline=True
            )
        except KeyError:
            continue
        if rating < 4.0:  # reduce the number of messages per day
            continue

        try:
            embed.add_field(
                name='Release Date',
                value=game['human'],
                inline=True
            )
        except KeyError:
            pass

        try:
            embed.set_thumbnail(url=f"https:{game['game']['cover']['url'].replace('_thumb', '_original')}")
        except KeyError:
            pass

        try:
            embed.set_image(url=f"https:{game['game']['artworks'][0]['url'].replace('_thumb', '_original')}")
        except KeyError:
            pass

        try:
            platforms = ', '.join(platform['name'] for platform in game['game']['platforms'])
            name = 'Platforms' if len(game['game']['platforms']) > 1 else 'Platform'

            embed.add_field(
                name=name,
                value=platforms,
                inline=False
            )
        except KeyError:
            pass

        try:
            genres = ', '.join(genre['name'] for genre in game['game']['genres'])
            name = 'Genres' if len(game['game']['genres']) > 1 else 'Genre'

            embed.add_field(
                name=name,
                value=genres,
                inline=False
            )
        except KeyError:
            pass

        embed.set_author(
            name=bot_name,
            url=bot_url,
            icon_url=avatar
        )

        embed.set_footer(
            text='Data provided by IGDB',
            icon_url='https://www.igdb.com/favicon-196x196.png'
        )

        message = bot.send_message(channel_id=channel_id, embed=embed)
        thread = bot.create_thread(message=message, name=embed.title)

        print(f'thread created: {thread.name}')

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
