# standard imports
from datetime import datetime
from io import BytesIO
import json
import os
import random
import sys
from urllib import parse

# lib imports
import discord
from discord.commands import Option, OptionChoice
from discord.ext import tasks
from igdb.wrapper import IGDBWrapper
from libgravatar import Gravatar
import requests

# local imports
import keep_alive

# development imports
from dotenv import load_dotenv
load_dotenv(override=False)  # environment secrets take priority over .env file

# env variables
READTHEDOCS_TOKEN = os.environ['READTHEDOCS_TOKEN']

# convert month number to igdb human-readable month
month_dictionary = {
    1: 'Jan',
    2: 'Feb',
    3: 'Mar',
    4: 'Apr',
    5: 'May',
    6: 'Jun',
    7: 'Jul',
    8: 'Aug',
    9: 'Sep',
    10: 'Oct',
    11: 'Nov',
    12: 'Dec'
}


def get_bot_avatar(gravatar: str) -> str:
    """Return the gravatar of a given email.

    :param gravatar: the gravatar email
    :return: url to image
    """

    g = Gravatar(email=gravatar)
    image_url = g.get_image()

    return image_url


def discord_message(git_user: str, git_repo: str, wiki_file: str, color: int):
    """Return the elements of a the discord message from the given parameters.

    :param git_user: Github username
    :param git_repo: Github repo name
    :param wiki_file: Wiki page filename
    :param color: hex color code
    :return: url, embed message, color
    """
    url = f'https://github.com/{git_user}/{git_repo}/wiki/{wiki_file}'
    embed_message = convert_wiki(git_user=git_user, git_repo=git_repo, wiki_file=wiki_file)
    if len(embed_message) > 2048:
        see_more = f'...\n\n...See More on [Github]({url})'
        embed_message = f'{embed_message[:2048 - len(see_more)]}{see_more}'
    return url, embed_message, color


def igdb_authorization(client_id: str, client_secret: str) -> dict:
    """Return an authorization dictionary for the IGDB api.

    :param client_id: IGDB client id
    :param client_secret: IGDB client secret
    :return: authorization dictionary
    """
    grant_type = 'client_credentials'

    auth_headers = {
                'Accept': 'application/json',
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': grant_type
            }

    token_url = 'https://id.twitch.tv/oauth2/token'

    authorization = post_json(url=token_url, headers=auth_headers)
    return authorization


def post_json(url: str, headers: dict) -> dict:
    """
    Make a post request in json format to the given URL using the given headers.

    :param url: URL for post request
    :param headers: Headers for post request
    :return: result
    """
    result = requests.post(url=url, data=headers).json()
    return result


# constants
bot_token = os.environ['BOT_TOKEN']
bot = discord.Bot(intents=discord.Intents.all(), auto_sync_commands=True)

org_name = 'LizardByte'
bot_name = f'{org_name}-Bot'
bot_url = 'https://app.lizardbyte.dev'

# avatar
avatar = get_bot_avatar(gravatar=os.environ['GRAVATAR_EMAIL'])

response = requests.get(url=avatar)
avatar_img = BytesIO(response.content).read()

# context reference
# https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.ext.commands.Context

# get list of guild ids from file
guild_file = 'guilds.json'
try:
    with open(file=guild_file, mode='r') as f:
        guild_ids = json.load(fp=f)
except FileNotFoundError:
    guild_ids = []


@bot.event  # on ready
async def on_ready():
    """
    On Ready event.

    - Update guild_file with guild ids
    - Change the bot presence
    - Start daily tasks
    """
    print(f'py-cord version: {discord.__version__}')
    print(f'Logged in as || name: {bot.user.name} || id: {bot.user.id}')
    print(f'Servers connected to: {bot.guilds}')

    for guild in bot.guilds:
        print(guild.name)
        if guild.id not in guild_ids:
            guild_ids.append(guild.id)
    with open(file=guild_file, mode='w') as file:
        json.dump(obj=guild_ids, fp=file, indent=2)

    # update the username and avatar
    await bot.user.edit(username=bot_name, avatar=avatar_img)

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name=f"the {org_name} server")
    )

    try:
        os.environ['DAILY_TASKS']
    except KeyError:
        daily_task.start()
    else:
        if os.environ['DAILY_TASKS'].lower() == 'true':
            daily_task.start()
        else:
            print("'DAILY_TASKS' environment variable is disabled")


@bot.slash_command(name="help",
                   description=f"Get help with {bot_name}",
                   guild_ids=guild_ids,
                   )
async def help_command(ctx):
    """
    Send an embed with help information to the server and channel where the command was issued.
    :param ctx: request message context
    :return: embed
    """
    description = f"""\
    `/help` - Print this message.
    
    `/docs <req:project> <opt:version> <opt:user>` - Return url to project docs.
    `project` - The project to return docs for. Required.
    `version` - The version of the docs to return. Optional.
    `user` - The user to mention in the response. Optional.
    
    `/donate <opt:user>` - See how to support {org_name}.
    `user` - The user to mention in the response. Optional.
    
    `/random <opt:user>` - Return a random video game quote.
    `user` - The user to mention in the response. Optional.
    """

    embed = discord.Embed(description=description, color=0xE5A00D)
    embed.set_footer(text=bot_name, icon_url=avatar)

    await ctx.respond(embed=embed)


@bot.slash_command(name="donate",
                   description=f"Support the development of {org_name}",
                   guild_ids=guild_ids,
                   )
async def donate_command(ctx, user: Option(discord.Member, description='Select the user to mention') = None):
    """
    Sends embeds with donate information to the server and channel where the command was issued.
    :param ctx: request message context
    :param user: username to mention in response
    :return: embeds
    """
    embeds = []

    embeds.append(discord.Embed(color=0x333))
    embeds[-1].set_author(
        name='Github Sponsors',
        url=f'https://github.com/sponsors/{org_name}',
        icon_url='https://github.com/fluidicon.png'
    )

    embeds.append(discord.Embed(description='Includes Discord benefits.', color=0x60D1F6))
    embeds[-1].set_author(
        name='MEE6',
        url='https://mee6.xyz/m/804382334370578482',
        icon_url='https://mee6.xyz/icons-decf734e1b14376075878ea568aa8d3b/apple-touch-icon-180x180.png'
    )

    embeds.append(discord.Embed(description='Includes Discord benefits.', color=0xf96854))
    embeds[-1].set_author(
        name='Patreon',
        url=f'https://www.patreon.com/{org_name}',
        icon_url='https://c5.patreon.com/external/favicon/apple-touch-icon.png?v=jw6AR4Rg74'
    )

    embeds.append(discord.Embed(color=0x003087))
    embeds[-1].set_author(
        name='PayPal',
        url='https://paypal.me/ReenigneArcher',
        icon_url='https://www.paypalobjects.com/webstatic/icon/pp196.png'
    )

    if user:
        await ctx.respond(f'Thank you for your support {user.mention}!',
                          embeds=embeds)
    else:
        await ctx.respond('Thank you for your support!',
                          embeds=embeds)


@bot.slash_command(name="random",
                   description="Random video game quote",
                   guild_ids=guild_ids,
                   )
async def random_command(ctx, user: Option(discord.Member, description='Select the user to mention') = None):
    """
    Send an embed with a random quote to the server and channel where the command was issued.
    :param ctx: request message context
    :param user: username to mention in response
    :return: embed
    """
    quotes = requests.get(url='https://app.lizardbyte.dev/uno/random-quotes/games.json').json()

    quote_index = random.choice(seq=quotes)
    quote = quote_index['quote']

    game = quote_index['game']
    character = quote_index['character']

    if game and character:
        description = f'~{character} / {game}'
    elif game:
        description = f'{game}'
    elif character:
        description = f'~{character}'
    else:
        description = None

    embed = discord.Embed(title=quote, description=description, color=0x00ff00)
    embed.set_footer(text=bot_name, icon_url=avatar)

    if user:
        await ctx.respond(user.mention, embed=embed)
    else:
        await ctx.respond(embed=embed)


# get projects list from readthedocs
def get_readthedocs() -> list:
    url_base = 'https://readthedocs.org'
    url = f'{url_base}/api/v3/projects/'
    headers = {'Authorization': f'token {READTHEDOCS_TOKEN}'}

    results = []

    while True:
        res = requests.get(url, headers=headers)
        data = res.json()

        results.extend(data['results'])

        if data['next']:
            url = f"{url_base}{data['next']}"
        else:
            break

    return results


def get_readthedocs_names() -> list:
    names = []

    projects = get_readthedocs()
    for project in projects:
        names.append(project['name'])

    return names


@bot.slash_command(name="docs",
                   description="Return docs for any project.",
                   guild_ids=guild_ids,
                   )
async def docs_command(ctx,
                       project: Option(str,
                                       description='Select the project',
                                       choices=get_readthedocs_names(),
                                       required=True
                                       ),
                       version: Option(str,
                                       description='Documentation for which version',
                                       choices=['latest', 'nightly'],
                                       required=False
                                       ) = 'latest',
                       user: Option(discord.Member,
                                    description='Select the user to mention'
                                    ) = None
                       ):
    """
    Send an embed with a project documentation.
    :param ctx: request message context
    :param project: the project
    :param version: the version of the documentation
    :param user: username to mention in response
    :return: embed
    """
    readthedocs = get_readthedocs()
    project_url = None
    for docs in readthedocs:
        if project == docs['name']:
            project_url = docs['urls']['documentation']
            break

    if project_url:
        project_url = project_url.replace('/en/latest/', f'/en/{version}/')

        description = f"""\
        Here is the `{version}` documentation for `{project}`.
        """

        embed = discord.Embed(title=project_url, url=project_url, description=description, color=0x00ff00)
        embed.set_footer(text=bot_name, icon_url=avatar)

        if user:
            await ctx.respond(user.mention, embed=embed)
        else:
            await ctx.respond(embed=embed)


@tasks.loop(minutes=60.0)
async def daily_task():
    """
    Functions to run on a schedule.

    - Create an embed and thread for each game released on this day in history, if enabled.
    """
    if datetime.utcnow().hour == int(os.getenv(key='daily_tasks_utc_hour', default=12)):
        daily_releases = False
        try:
            os.environ['DAILY_RELEASES']
        except KeyError:
            daily_releases = True
        else:
            if os.environ['DAILY_RELEASES'].lower() == 'true':
                daily_releases = True
            else:
                print("'DAILY_RELEASES' environment variable is disabled")

        if daily_releases:
            try:
                channel = bot.get_channel(int(os.environ['DAILY_CHANNEL_ID']))
            except KeyError:
                print("'DAILY_CHANNEL_ID' not defined in environment variables.")
            else:
                igdb_auth = igdb_authorization(client_id=os.environ['IGDB_CLIENT_ID'],
                                               client_secret=os.environ['IGDB_CLIENT_SECRET'])
                wrapper = IGDBWrapper(client_id=os.environ['IGDB_CLIENT_ID'], auth_token=igdb_auth['access_token'])

                end_point = 'release_dates'
                fields = 'human, game.name, game.summary, game.url, game.genres.name, game.rating, game.cover.url, game.artworks.url, game.platforms.name, game.platforms.url'
                where = f'human="{month_dictionary[datetime.utcnow().month]} {datetime.utcnow().day:02d}"*'
                limit = 500
                query = f'fields {fields}; where {where}; limit {limit};'

                byte_array = bytes(wrapper.api_request(endpoint=end_point, query=query))
                json_result = json.loads(byte_array)
                # print(json.dumps(json_result, indent=2))

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
                            description=game['game']['summary'][0:2000-1],
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

                        if rating < 4.0:  # reduce number of messages per day
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
                        platforms = ''
                        name = 'Platform'

                        for platform in game['game']['platforms']:
                            if platforms:
                                platforms += ", "
                                name = 'Platforms'
                            platforms += platform['name']

                        embed.add_field(
                            name=name,
                            value=platforms,
                            inline=False
                        )
                    except KeyError:
                        pass

                    try:
                        genres = ''
                        name = 'Genre'

                        for genre in game['game']['genres']:
                            if genres:
                                genres += ", "
                                name = 'Genres'
                            genres += genre['name']

                        embed.add_field(
                            name=name,
                            value=genres,
                            inline=False
                        )
                    except KeyError:
                        pass

                    try:
                        embed.set_author(
                            name=bot_name,
                            url=bot_url,
                            icon_url=avatar
                        )
                    except KeyError:
                        pass

                    embed.set_footer(
                        text='Data provided by IGDB',
                        icon_url='https://www.igdb.com/favicon-196x196.png'
                    )

                    message = await channel.send(embed=embed)
                    thread = await message.create_thread(name=embed.title)

                    print(f'thread created: {thread.name}')

# to run in replit
try:
    os.environ['REPL_SLUG']
except KeyError:
    pass  # not running in replit
else:
    keep_alive.keep_alive()  # Start the web server

try:
    bot.loop.run_until_complete(future=bot.start(token=bot_token))  # Login the bot
except KeyboardInterrupt:
    print("Keyboard Interrupt Detected")
finally:
    print("Attempting to stop daily tasks")
    daily_task.stop()
    print("Attempting to close bot connection")
    bot.loop.run_until_complete(future=bot.close())
    print("Closed bot")
