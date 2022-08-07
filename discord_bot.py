# standard imports
from datetime import datetime
from io import BytesIO
import json
import os
import random
from typing import Union

# lib imports
from bs4 import BeautifulSoup
import discord
from discord.commands import Option
from discord.ext import tasks
from discord.ui.select import Select
from igdb.wrapper import IGDBWrapper
from libgravatar import Gravatar
import requests

# local imports
import keep_alive

# development imports
from dotenv import load_dotenv
load_dotenv(override=False)  # environment secrets take priority over .env file

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
    """
    Get Gravatar image url.

    Return the Gravatar image url of the given email address.

    Parameters
    ----------
    gravatar : str
        The Gravatar email address.

    Returns
    -------
    str
        Gravatar image url.
    """

    g = Gravatar(email=gravatar)
    image_url = g.get_image()

    return image_url


def igdb_authorization(client_id: str, client_secret: str) -> dict:
    """
    Authorization for IGDB.

    Return an authorization dictionary for the IGDB api.

    Parameters
    ----------
    client_id : str
        IGDB/Twitch API client id.
    client_secret : str
        IGDB/Twitch client secret.

    Returns
    -------
    dict
        Authorization dictionary.
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


def get_json(url: str) -> Union[dict, list]:
    """
    Make a GET request and get the response in json.

    Makes a GET request to the given url.

    Parameters
    ----------
    url : str
        The url for the GET request.

    Returns
    -------
    any
        The json response.
    """
    res = requests.get(url=url)
    data = res.json()

    return data


def post_json(url: str, headers: dict) -> Union[dict, list]:
    """
    Make a POST request and get response in json.

    Makes a POST request with given headers to the given url.

    Parameters
    ----------
    url : str
        The url for the POST request.
    headers : dict
        Headers for the POST request.

    Returns
    -------
    any
        The json response.
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
# https://docs.pycord.dev/en/master/ext/commands/api.html#discord.ext.commands.Context

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
    Bot on ready event.

    This function runs when the discord bot is ready. The function will update the ``guilds.json`` file, update the bot
    present, update the username and avatar, and start daily tasks.
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
                   description=f"Support the development of {org_name}",
                   guild_ids=guild_ids,
                   )
async def donate_command(ctx: discord.ApplicationContext,
                         user: Option(
                             input_type=discord.Member,
                             description='Select the user to mention') = None
                         ):
    """
    The ``donate`` slash command.

    Sends a discord embed, with information on how to donate to the project, to the server and channel where the
    command was issued.

    Parameters
    ----------
    ctx : discord.ApplicationContext
        Request message context.
    user : discord.Commands.Option
        Username to mention in response.
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
async def random_command(ctx: discord.ApplicationContext,
                         user: Option(
                             input_type=discord.Member,
                             description='Select the user to mention') = None
                         ):
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


class DocsCommandDefaultProjects(object):
    """
    Class representing default projects for ``docs`` slash command.

    Attributes
    ----------
    self.projects : Union[dict, list]
        The json representation of our readthedocs projects.
    self.project_options : list
        A list of `discord.SelectOption` objects.
    """
    def __init__(self):
        self.projects = get_json(url='https://app.lizardbyte.dev/uno/readthedocs/projects.json')
        self.projects_options = []
        for project in self.projects:
            try:
                parent_project = project['subproject_of']['name']
            except (KeyError, TypeError):
                parent_project = None

            self.projects_options.append(
                discord.SelectOption(label=project['name'],
                                     value=project['repository']['url'].rsplit('/', 1)[-1].rsplit('.git', 1)[0],
                                     description=f"Subproject of {parent_project}" if parent_project else None)
            )


class DocsCommandView(discord.ui.View):
    """
    Class representing `discord.ui.View` for ``docs`` slash command.

    Attributes
    ----------
    self.ctx : discord.ApplicationContext
        Request message context.
    self.docs_project : str
        The project name.
    self.docs_version : str
        The url to the documentation of the selected version.
    self.docs_category : str
        The name of the selected category.
    self.docs_page : str
        The name of the selected page.
    self.docs_section : str
        The name of the selected section.
    self.html : bytes
        Content of `requests.get()` in bytes.
    self.soup : bs4.BeautifulSoup
        BeautifulSoup object of `self.html`
    self.toc : ResultSet
        Docs table of contents.
    self.categories : list
        A list of Docs categories.
    self.pages : list
        A list of pages for the selected category.
    self.sections : list
        A list of sections for the selected page.
    """
    def __init__(self, ctx: discord.ApplicationContext):
        super().__init__(timeout=60)

        self.ctx = ctx

        # final values
        self.docs_project = None
        self.docs_version = None
        self.docs_category = None
        self.docs_page = None
        self.docs_section = None

        # intermediate values
        self.html = None
        self.soup = None
        self.toc = None
        self.categories = None
        self.pages = None
        self.sections = None

    # timeout is not working, see: https://github.com/Pycord-Development/pycord/issues/1549
    # async def on_timeout(self):
    #     """
    #     Timeout callback.
    #
    #     Disable children items, and edit the original message.
    #     """
    #     for child in self.children:
    #         child.disabled = True
    #
    #     embed = discord.Embed(title="...", color=0xDC143C)
    #     embed.set_footer(text=bot_name, icon_url=avatar)
    #     await self.message.edit(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Check the interaction.

        Ensure the user interacting with the interaction is the user that initiated it.

        Parameters
        ----------
        interaction : discord.Interaction

        Returns
        -------
        bool
            If interaction user is the author or bot owner return ``True``, otherwise ``False``.
        """
        if interaction.user and interaction.user.id in (self.ctx.bot.owner_id, self.ctx.author.id):
            return True
        else:
            await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!',
                                                    ephemeral=True)
            return False

    async def callback(self, select: Select, interaction: discord.Interaction):
        """
        Callback for select menus of `docs` command.

        Updates Select Menus depending on currently selected values. Updates embed message when requirements are met.

        Parameters
        ----------
        select : discord.ui.select.Select
            The `Select` object interacted with.
        interaction : discord.Interaction
            The original discord interaction object.
        """
        select_index = None
        index = 0
        for child in self.children:
            if child == select:
                select_index = index  # this is the current child... user interacted with this child

            # disable dependent drop downs
            if select_index is not None:
                if index - select_index - 1 <= 0:  # add 1 to select index to always allow subtracting
                    child.disabled = False
                else:
                    child.disabled = True
                    child.options = [discord.SelectOption(label='error')]

                if index - select_index == 1:  # this is the next child
                    child.options = [discord.SelectOption(label='0')]

                    if child == self.children[1]:  # choose docs version
                        readthedocs = self.children[0].values[0]

                        versions = get_json(
                            url=f'https://app.lizardbyte.dev/uno/readthedocs/versions/{readthedocs}.json')

                        options = []
                        for version in versions:
                            if version['active'] and version['built']:
                                options.append(discord.SelectOption(
                                    label=version['slug'],
                                    value=version['urls']['documentation'],
                                    description=f"Docs for {version['slug']} {version['type']}"
                                ))

                        child.options = options

                    if child == self.children[2]:  # choose the docs category
                        url = self.children[1].values[0]

                        self.html = requests.get(url=url).content
                        self.soup = BeautifulSoup(self.html, 'html.parser')

                        self.toc = self.soup.select("div[class*=toctree-wrapper]")

                        self.categories = []
                        for item in self.toc:
                            self.categories.extend(item.select("p[role=heading]"))

                        options = [discord.SelectOption(label='None')]
                        for category in self.categories:

                            options.append(discord.SelectOption(
                                label=category.string
                            ))

                        child.options = options

                    if child == self.children[3]:  # choose the docs page
                        category_value = self.children[2].values[0]

                        for category in self.categories:
                            if category.string == category_value:
                                category_section = self.toc[self.categories.index(category)]

                                page_sections = category_section.findChild('ul')
                                self.sections = page_sections.find_all('li', class_="toctree-l1")

                                break

                        options = []
                        self.pages = []
                        if category_value == 'None':
                            options.append(discord.SelectOption(label='None', value=category_value, default=True))

                            # enable the final menu
                            self.children[-1].disabled = False
                            self.children[-1].options = options
                        else:
                            for section in self.sections:
                                page = section.findNext('a')
                                self.pages.append(page)

                                options.append(discord.SelectOption(
                                    label=page.string,
                                    value=page['href']
                                ))

                        child.options = options

                        if category_value == 'None':
                            break

                    if child == self.children[4]:  # choose the docs page section
                        page_value = self.children[3].values[0]

                        if page_value == 'None':
                            options = [discord.SelectOption(label='None', value=page_value, default=True)]
                        else:
                            options = [discord.SelectOption(label='None', value=page_value)]
                            for section in self.sections:
                                page = section.findNext('a')
                                if page_value == page['href']:
                                    page_sections = section.find_all('a')
                                    del page_sections[0]  # delete first item from list

                                    for page_section in page_sections:
                                        options.append(discord.SelectOption(
                                            label=page_section.string,
                                            value=page_section['href']
                                        ))

                        child.options = options

            index += 1

        # set the currently selected value to the default item
        for option in select.options:
            if option.value == select.values[0]:
                option.default = True
            else:
                option.default = False

        # reset values
        try:
            self.docs_project = self.children[0].values[0]
            self.docs_version = self.children[1].values[0]

            if self.children[2].values[0] == 'None':
                self.docs_category = ''
                self.docs_page = ''
                self.docs_section = ''
            else:
                self.docs_category = self.children[2].values[0]
                self.docs_page = self.children[3].values[0] if self.children[3].values[0] != 'None' else ''
                self.docs_section = self.children[4].values[0] if self.children[4].values[0] != 'None' else ''
        except IndexError:
            pass
        if select == self.children[0]:  # chose the docs project
            self.docs_version = None
            self.docs_category = None
            self.docs_page = None
            self.docs_section = None
        elif select == self.children[1]:  # chose the docs version
            self.docs_category = None
            self.docs_page = None
            self.docs_section = None
        elif select == self.children[2]:  # chose the docs category
            self.docs_page = None
            self.docs_section = None
        elif select == self.children[3]:  # chose the docs page
            self.docs_section = None

        # get the original embed
        embed = interaction.message.embeds[0]  # we know there is only 1 embed

        if self.docs_project and self.docs_version:  # the project and version are selected
            url = f'{self.docs_version}{self.docs_section}'

            if self.docs_category is not None:  # category has a value, which may be ""
                if self.docs_category:  # category is selected, so the next item must not be blank
                    if self.docs_page is not None and self.docs_section is not None:  # info is complete
                        embed.title = f'{self.docs_project} | {self.docs_category}'
                        embed.description = f'The selected docs are available at {url}'
                        embed.color = 0x39FF14  # PyCharm complains that the color is read only, but this works anyway
                        embed.url = url

                        await interaction.response.edit_message(embed=embed, view=self)
                        return
                else:  # info is complete IF category is ""
                    embed.title = f'{self.docs_project} | {self.docs_category}'
                    embed.description = f'The selected docs are available at {url}'
                    embed.color = 0x39FF14  # PyCharm complains that the color is read only, but this works anyway
                    embed.url = url

                    await interaction.response.edit_message(embed=embed, view=self)
                    return

        # info is not complete
        embed.title = "Select the remaining values"
        embed.description = None
        embed.color = 0xDC143C
        embed.url = None

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(
        placeholder="Choose docs...",
        disabled=False,
        min_values=1,
        max_values=1,
        options=DocsCommandDefaultProjects().projects_options
    )
    async def slug_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select, interaction)

    @discord.ui.select(
        placeholder="Choose version...",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label='error')]
    )
    async def version_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select=select, interaction=interaction)

    @discord.ui.select(
        placeholder="Choose category...",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label='error')]
    )
    async def category_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select=select, interaction=interaction)

    @discord.ui.select(
        placeholder="Choose page...",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label='error')]
    )
    async def page_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select=select, interaction=interaction)

    @discord.ui.select(
        placeholder="Choose section...",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label='error')]
    )
    async def section_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select=select, interaction=interaction)


@bot.slash_command(name="docs",
                   description="Return docs for any project.",
                   guild_ids=guild_ids,
                   )
async def docs_command(ctx: discord.ApplicationContext,
                       user: Option(discord.Member,
                                    description='Select the user to mention'
                                    ) = None
                       ):
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
    embed = discord.Embed(title="Select a project", color=0xDC143C)
    embed.set_footer(text=bot_name, icon_url=avatar)

    if user:
        await ctx.respond(f'{ctx.author.mention}, {user.mention}', embed=embed, view=DocsCommandView(ctx=ctx))
    else:
        await ctx.respond(f'{ctx.author.mention}', embed=embed, view=DocsCommandView(ctx=ctx))


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
