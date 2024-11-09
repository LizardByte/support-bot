# standard imports
from datetime import datetime, UTC
import json
import os

# lib imports
import discord
from discord.ext import tasks
from igdb.wrapper import IGDBWrapper

# local imports
from src.common.common import avatar, bot_name, bot_url
from src.common import sponsors
from src.discord.bot import Bot
from src.discord.helpers import igdb_authorization, month_dictionary


@tasks.loop(minutes=60.0)
async def daily_task(bot: Bot):
    """
    Run daily task loop.

    This function runs on a schedule, every 60 minutes. Create an embed and thread for each game released
    on this day in history (according to IGDB), if enabled.
    """
    if datetime.now(UTC).hour != int(os.getenv(key='DAILY_TASKS_UTC_HOUR', default=12)):
        return

    daily_releases = True if os.getenv(key='DAILY_RELEASES', default='true').lower() == 'true' else False
    if not daily_releases:
        print("'DAILY_RELEASES' environment variable is disabled")
        return

    try:
        channel = bot.get_channel(int(os.environ['DAILY_CHANNEL_ID']))
    except KeyError:
        print("'DAILY_CHANNEL_ID' not defined in environment variables.")
        return

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

    where = f'human="{month_dictionary[datetime.now(UTC).month]} {datetime.now(UTC).day:02d}"*'
    limit = 500
    query = f'fields {", ".join(fields)}; where {where}; limit {limit};'

    byte_array = bytes(wrapper.api_request(endpoint=end_point, query=query))
    json_result = json.loads(byte_array)

    game_ids = []

    for game in json_result:
        color = 0x9147FF

        try:
            game_id = game['game']['id']
        except KeyError:
            continue
        else:
            if game_id not in game_ids:
                game_ids.append(game_id)
            else:  # do not repeat the same game... even though it could be a different platform
                continue

        try:
            embed = discord.Embed(
                title=game['game']['name'],
                url=game['game']['url'],
                description=game['game']['summary'][0:2000 - 1],
                color=color
            )
        except KeyError:
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
            rating = round(game['game']['rating'] / 20, 1)
            embed.add_field(
                name='Average Rating',
                value=f'⭐{rating}',
                inline=True
            )

            if rating < 4.0:  # reduce the number of messages per day
                continue
        except KeyError:
            continue

        try:
            embed.set_thumbnail(
                url=f"https:{game['game']['cover']['url'].replace('_thumb', '_original')}"
            )
        except KeyError:
            pass

        try:
            embed.set_image(
                url=f"https:{game['game']['artworks'][0]['url'].replace('_thumb', '_original')}"
            )
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

        message = await channel.send(embed=embed)
        thread = await message.create_thread(name=embed.title)

        print(f'thread created: {thread.name}')


@tasks.loop(minutes=1.0)
async def hourly_task(bot: Bot):
    """
    Run hourly task loop.

    This function runs on a schedule, every 1 minute.
    If the current time is not at the top of the hour, return.
    """
    if datetime.now(UTC).minute != 0:
        return

    # check each user in the database for their GitHub sponsor status
    with bot.db as db:
        discord_users = db.get('discord_users', {})

    if not discord_users:
        return

    github_sponsors = sponsors.get_github_sponsors()

    for user_id, user_data in discord_users.items():
        # check if the user is a GitHub sponsor
        for edge in github_sponsors['data']['organization']['sponsorshipsAsMaintainer']['edges']:
            sponsor = edge['node']['sponsorEntity']
            if sponsor['login'] == user_data['github_username']:
                # user is a sponsor
                user_data['github_sponsor'] = True

                monthly_amount = edge['node'].get('tier', {}).get('monthlyPriceInDollars', 0)

                for tier, amount in sponsors.tier_map.items():
                    if monthly_amount >= amount:
                        user_data['sponsor_tiers'] = [tier, 'supporters']
                        break
                else:
                    user_data['sponsor_tiers'] = []
        else:
            # user is not a sponsor
            user_data['github_sponsor'] = False
            user_data['sponsor_tiers'] = []

        # update the discord user roles
        for g in bot.guilds:
            roles = g.roles

            role_map = {
                't4-sponsors': discord.utils.get(roles, name='t4-sponsors'),
                't3-sponsors': discord.utils.get(roles, name='t3-sponsors'),
                't2-sponsors': discord.utils.get(roles, name='t2-sponsors'),
                't1-sponsors': discord.utils.get(roles, name='t1-sponsors'),
                'supporters': discord.utils.get(roles, name='supporters'),
            }

            tiers = user_data['sponsor_tiers']

            for tier, role in role_map.items():
                role = role_map.get(tier, None)

                if role:
                    member = g.get_member(user_id)
                    if tier in tiers:
                        await member.add_roles(role)
                    else:
                        await member.remove_roles(role)
