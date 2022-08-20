# standard imports
from datetime import datetime
import json
import os
import random

# lib imports
import discord
from discord.commands import Option
from discord.ext import tasks
from igdb.wrapper import IGDBWrapper
import requests

# local imports
from discord_constants import org_name, bot_name, bot_url
from discord_helpers import igdb_authorization, month_dictionary
import keep_alive

# development imports
from dotenv import load_dotenv
load_dotenv(override=False)  # environment secrets take priority over .env file

if True:  # hack for flake8
    from discord_avatar import avatar, avatar_img
    from discord_views import DocsCommandView, DonateCommandView, RefundCommandView

# constants
bot_token = os.environ['BOT_TOKEN']
bot = discord.Bot(intents=discord.Intents.all(), auto_sync_commands=True)

user_mention_desc = 'Select the user to mention'

# context reference
# https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.ext.commands.Context
# https://docs.pycord.dev/en/master/ext/commands/api.html#discord.ext.commands.Context


@bot.event  # on ready
async def on_ready():
    """
    Bot on ready event.

    This function runs when the discord bot is ready. The function will update the bot presence, update the username
    and avatar, and start daily tasks.
    """
    print(f'py-cord version: {discord.__version__}')
    print(f'Logged in as || name: {bot.user.name} || id: {bot.user.id}')
    print(f'Servers connected to: {bot.guilds}')

    # update the username and avatar
    await bot.user.edit(username=bot_name, avatar=avatar_img)

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name=f"the {org_name} server")
    )

    bot.add_view(DonateCommandView())  # register view for persistent listening

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
                   description=f"Get help with {bot_name}"
                   )
async def help_command(ctx: discord.ApplicationContext):
    """
    The ``help`` slash command.

    Send a discord embed, with help information, to the server and channel where the command was issued.

    Parameters
    ----------
    ctx : discord.ApplicationContext
        Request message context.
    """
    description = f"""\
    `/help` - Print this message.

    `/docs <opt:user>` - Return url to project docs based on follow up questions.
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
                   description=f"Support the development of {org_name}"
                   )
async def donate_command(ctx: discord.ApplicationContext,
                         user: Option(input_type=discord.Member,
                                      description=user_mention_desc,
                                      required=False)):
    """
    The ``donate`` slash command.

    Sends a discord view, with various donation urls, to the server and channel where the
    command was issued.

    Parameters
    ----------
    ctx : discord.ApplicationContext
        Request message context.
    user : discord.Commands.Option
        Username to mention in response.
    """
    if user:
        await ctx.respond(f'Thank you for your support {user.mention}!', view=DonateCommandView())
    else:
        await ctx.respond('Thank you for your support!', view=DonateCommandView())


@bot.slash_command(name="random",
                   description="Random video game quote"
                   )
async def random_command(ctx: discord.ApplicationContext,
                         user: Option(discord.Member,
                                      description=user_mention_desc,
                                      required=False)):
    """
    The ``random`` slash command.

    Sends a discord embed, with a random video game quote, to the server and channel where the command was issued.

    Parameters
    ----------
    ctx : discord.ApplicationContext
        Request message context.
    user : discord.Commands.Option
        Username to mention in response.
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


@bot.slash_command(name="docs",
                   description="Return docs for any project."
                   )
async def docs_command(ctx: discord.ApplicationContext,
                       user: Option(discord.Member,
                                    description=user_mention_desc,
                                    required=False)):
    """
    The ``docs`` slash command.

    Sends a discord embed, with `Select Menus` allowing the user to select the specific documentation,
    to the server and channel where the command was issued.

    Parameters
    ----------
    ctx : discord.ApplicationContext
        Request message context.
    user : discord.Commands.Option
        Username to mention in response.
    """
    embed = discord.Embed(title="Select a project", color=0xF1C232)
    embed.set_footer(text=bot_name, icon_url=avatar)

    if user:
        await ctx.respond(
            f'{ctx.author.mention}, {user.mention}',
            embed=embed,
            ephemeral=False,
            view=DocsCommandView(ctx=ctx)
        )
    else:
        await ctx.respond(
            f'{ctx.author.mention}',
            embed=embed,
            ephemeral=False,
            view=DocsCommandView(ctx=ctx)
        )


@bot.slash_command(name="refund",
                   description="Refund form for unhappy customers."
                   )
async def refund_command(ctx: discord.ApplicationContext,
                         user: Option(discord.Member,
                                      description=user_mention_desc,
                                      required=False)):
    """
    The ``refund`` slash command.

    Sends a discord embed, with a `Modal`, to the server and channel where the command was issued. This command is
    pure satire.

    Parameters
    ----------
    ctx : discord.ApplicationContext
        Request message context.
    user : discord.Commands.Option
        Username to mention in response.
    """
    embed = discord.Embed(title="Refund request",
                          description="Original purchase price: $0.00\n\n"
                                      "Select the button below to request a full refund!",
                          color=0xDC143C)
    embed.set_footer(text=bot_name, icon_url=avatar)

    if user:
        await ctx.respond(user.mention, embed=embed, view=RefundCommandView())
    else:
        await ctx.respond(embed=embed, view=RefundCommandView())


@tasks.loop(minutes=60.0)
async def daily_task():
    """
    Run daily task loop.

    This function runs on a schedule, every 60 minutes. Create an embed and thread for each game released
    on this day in history (according to IGDB), if enabled.
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

                where = f'human="{month_dictionary[datetime.utcnow().month]} {datetime.utcnow().day:02d}"*'
                limit = 500
                query = f'fields {", ".join(fields)}; where {where}; limit {limit};'

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
