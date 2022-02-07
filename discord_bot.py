import discord
from discord.commands import Option, OptionChoice
from discord.ext import tasks
from datetime import datetime
from igdb.wrapper import IGDBWrapper
import json
import os
import re
import requests
import sys
import urllib

# local imports
import keep_alive

# development imports
from dotenv import load_dotenv
load_dotenv(override=False)  # environment secrets take priority over .env file

# convert month number to igdb human readable month
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


def get_repl_avatar(user_name):
    url = f'https://replit.com/@{user_name}'
    repl_page = requests.get(url)

    image_link = re.search(
        r'property=\"og:image\" content=\"(https://storage\.googleapis\.com/replit/images/[a-z_0-9]*\.png)\"',
        repl_page.text
    ).group(1)

    return image_link


def convert_wiki(git_user, git_repo, wiki_file):
    url = f'https://raw.githubusercontent.com/wiki/{git_user}/{git_repo}/{wiki_file}.md'
    response = requests.get(url)

    return response.text


def discord_message(git_user, git_repo, wiki_file, color):
    url = f'https://github.com/{git_user}/{git_repo}/wiki/{wiki_file}'
    embed_message = convert_wiki(git_user, git_repo, wiki_file)
    if len(embed_message) > 2048:
        see_more = f'...\n\n...See More on [Github]({url})'
        embed_message = f'{embed_message[:2048 - len(see_more)]}{see_more}'
    return url, embed_message, color


def igdb_authorization(client_id, client_secret):
    grant_type = 'client_credentials'

    auth_headers = {
                'Accept': 'application/json',
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': grant_type
            }

    token_url = 'https://id.twitch.tv/oauth2/token'

    authorization = post_json(token_url, auth_headers)
    return authorization


def post_json(url, headers):
    result = requests.post(url=url, data=headers).json()
    return result


def main():
    # constants
    bot_token = os.environ['bot_token']
    bot = discord.Bot(intents=discord.Intents.all(), auto_sync_commands=True)
    # slash = SlashCommand(bot, sync_commands=True)

    bot_name = os.environ['REPL_SLUG']
    bot_url = 'https://RetroArcher.github.io'

    # repl avatar
    global repl_avatar
    repl_avatar = get_repl_avatar(os.environ['REPL_OWNER'])

    # context reference
    # https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.ext.commands.Context

    # get list of guild ids from file
    guild_file = 'guilds.json'
    try:
        with open(guild_file, 'r') as f:
            guild_ids = json.load(f)
    except FileNotFoundError:
        guild_ids = []

    # command : wiki-file
    command_file = 'commands.json'
    try:
        with open(command_file, 'r') as f:
            command_dict = json.load(f)
    except FileNotFoundError:
        print(f'Error: {command_file} not found')
        sys.exit(1)

    # on ready
    @bot.event
    async def on_ready():
        print(f'py-cord version: {discord.__version__}')
        print(f'Logged in as || name: {bot.user.name} || id: {bot.user.id}')
        print(f'Servers connected to: {bot.guilds}')
        print(f"Connected to {os.environ['REPL_SLUG']}!")

        guild_ids = []
        for guild in bot.guilds:
            print(guild.name)
            guild_ids.append(guild.id)
        with open(guild_file, 'w') as file:
            json.dump(guild_ids, file, indent=2)

        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="the RetroArcher server")
        )

        try:
            os.environ['daily_tasks']
        except KeyError:
            daily_task.start()
        else:
            if os.environ['daily_tasks'] == 'true':
                daily_task.start()
            else:
                print("'daily_tasks' environment variable is disabled")

    @bot.slash_command(name="help",
                       description="Get help with RetroArcher Bot",
                       guild_ids=guild_ids,
                       )
    async def help_command(ctx):
        description = """\
        `/help` - Print this message.
        
        `/donate <opt:user>` - See how to support RetroArcher.
        `user` - The user to mention in the response. Optional.
        
        `/random <opt:user>` - Return a random video game quote.
        `user` - The user to mention in the response. Optional.
        
        `/wiki <req:page> <opt:user>` - Return page from the RetroArcher wiki.
        `page` - The page to return. Required.
        `user` - The user to mention in the response. Optional.
        """

        embed = discord.Embed(description=description, color=0xE5A00D)
        embed.set_author(name=bot_name, url=bot_url, icon_url=repl_avatar)

        await ctx.respond(embed=embed)

    @bot.slash_command(name="donate",
                       description="Support the development of RetroArcher",
                       guild_ids=guild_ids,
                       )
    async def donate(ctx, user: Option(discord.Member, description='Select the user to mention') = None):
        embeds = []

        embeds.append(discord.Embed(color=0x333))
        embeds[-1].set_author(name='Github Sponsors',
                              url='https://github.com/sponsors/ReenigneArcher',
                              icon_url='https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
                              )

        embeds.append(discord.Embed(description='Includes Discord benefits.', color=0x60D1F6))
        embeds[-1].set_author(name='MEE6',
                              url='https://mee6.xyz/m/804382334370578482',
                              icon_url='https://mee6.xyz/icons-decf734e1b14376075878ea568aa8d3b/apple-touch-icon-180x180.png'
                              )

        embeds.append(discord.Embed(description='Includes Discord benefits.', color=0xf96854))
        embeds[-1].set_author(name='Patreon',
                              url='https://www.patreon.com/RetroArcher',
                              icon_url='https://th.bing.com/th/id/OIP.suF0Aufc2rX2gzgPB2mXpAHaHa?pid=ImgDet&rs=1'
                              )

        embeds.append(discord.Embed(color=0x003087))
        embeds[-1].set_author(name='PayPal',
                              url='https://paypal.me/ReenigneArcher',
                              icon_url='https://img.etimg.com/thumb/msid-60762134,width-300,imgsize-9757,resizemode-4/paypal-reduces-remittance-certificate-charges-by-50-for-small-sellers.jpg'
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
    async def random(ctx, user: Option(discord.Member, description='Select the user to mention') = None):
        """ Returns a random quote """
        import random
        quote_list = [
            "@!#?@!",
            "Ah shit, here we go again",
            "All Your Base Are Belong To Us",
            "Beyond the scope of Light, beyond the reach of Dark. What could possibly await us. And yet we seek it, insatiably.",
            "Bury me with my money!",
            "Did I ever tell you what the definition of insanity is?",
            "Do a barrel roll!",
            "Don't make a girl a promise... If you know you can't keep it.",
            "Finish Him!",
            "Get over here!",
            "Hell, it's about time",
            "Hello, my friend. Stay awhile and listen.",
            "Hey! Listen!",
            "I gotta believe!!",
            "I need a weapon.",
            "I used to be an adventurer like you. Then I took an arrow in the knee.",
            "I want to restore this world, but I fear I can't do it alone. Perhaps you could give me a hand?",
            "It is pitch black. You are likely to be eaten by a grue.",
            "It’s dangerous to go alone, take this!",
            "It’s easy to forget what a sin is in the middle of a battlefield.",
            "It's time to kick ass and chew bubblegum... and I'm all outta gum.",
            "No Gods or Kings, only Man",
            "Nothing is true, everything is permitted.",
            "Reticulating splines",
            "Sir. Finishing this fight.",
            "Stand by for Titanfall",
            "The Cake Is a Lie",
            "Thank you Mario! But our Princess is in another castle!",
            "Thought I'd Try Shooting My Way Out—Mix Things Up A Little.",
            "Wake me... when you need me.",
            "War Never Changes",
            "We all make choices, but in the end our choices make us.",
            "We should start from the first floor, okay? And, Jill, here's a lock pick. It might be handy if you, the master of unlocking, take it with you.",
            "Well, butter my biscuits!",
            "Wololo",
            "Would you kindly?",
            "Yes sir, I need a weapon.",
            "You've got a heart of gold. Don't let them take it from you.",
            "You have died of dysentery.",
            "You must construct additional pylons.",
        ]

        quote = random.choice(quote_list)

        embed = discord.Embed(description=quote, color=0xE5A00D)
        embed.set_author(name=bot_name, url=bot_url, icon_url=repl_avatar)

        if user:
            await ctx.respond(user.mention, embed=embed)
        else:
            await ctx.respond(embed=embed)

    # Combine all wiki pages into one slash command with options/choices
    # Wiki Command
    wiki_choices = []
    for key, value in command_dict.items():
        wiki_choices.append(OptionChoice(name=key, value=key))

    @bot.slash_command(name="wiki",
                       description="Return any of the listed Wiki pages as a message.",
                       guild_ids=guild_ids,
                       )
    async def wiki(ctx,
                   page: Option(str,
                                description='Select the wiki page',
                                choices=wiki_choices,
                                required=True
                                ),
                   user: Option(discord.Member,
                                description='Select the user to mention'
                                ) = None
                   ):
        v = command_dict[page]

        git_user = 'RetroArcher'
        git_repo = 'RetroArcher.bundle'
        wiki_file = urllib.parse.quote(v)
        title = v.replace('-', ' ').replace('_', ' ').strip()
        color = 0xE5A00D

        url, embed_message, color = discord_message(git_user, git_repo, wiki_file, color)
        embed = discord.Embed(title=title, url=url, description=embed_message, color=color)
        embed.set_author(name=bot_name, url=bot_url, icon_url=repl_avatar)

        if user:
            await ctx.respond(user.mention, embed=embed)
        else:
            await ctx.respond(embed=embed)

    @tasks.loop(minutes=60.0)
    async def daily_task():
        if datetime.utcnow().hour == int(os.getenv(key='daily_tasks_utc_hour', default=12)):
            daily_releases = False
            try:
                os.environ['daily_releases']
            except KeyError:
                daily_releases = True
            else:
                if os.environ['daily_tasks'] == 'true':
                    daily_releases = True
                else:
                    print("'daily_releases' environment variable is disabled")

            if daily_releases:
                try:
                    channel = bot.get_channel(int(os.environ['daily_channel_id']))
                except KeyError:
                    print("'daily_channel_id' not defined in environment variables.")
                else:
                    igdb_auth = igdb_authorization(client_id=os.environ['igdb_client_id'],
                                                   client_secret=os.environ['igdb_client_secret'])
                    wrapper = IGDBWrapper(os.environ['igdb_client_id'], igdb_auth['access_token'])

                    end_point = 'release_dates'
                    fields = 'human, game.name, game.summary, game.url, game.genres.name, game.rating, game.cover.url, game.artworks.url, game.platforms.name, game.platforms.url'
                    where = f'human="{month_dictionary[datetime.utcnow().month]} {datetime.utcnow().day:02d}"*'
                    limit = 500
                    query = f'fields {fields}; where {where}; limit {limit};'

                    byte_array = wrapper.api_request(
                        end_point,
                        query
                    )
                    json_result = json.loads(byte_array)
                    # print(json.dumps(json_result, indent=2))

                    game_ids = []

                    for game in json_result:
                        color = 0x9147FF

                        try:
                            game_id = game['game']['id']
                        except KeyError as e:
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
                        except KeyError as e:
                            continue

                        try:
                            embed.add_field(
                                name='Release Date',
                                value=game['human'],
                                inline=True
                            )
                        except KeyError as e:
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
                        except KeyError as e:
                            continue

                        try:
                            embed.set_thumbnail(
                                url=f"https:{game['game']['cover']['url'].replace('_thumb', '_original')}"
                            )
                        except KeyError as e:
                            pass

                        try:
                            embed.set_image(
                                url=f"https:{game['game']['artworks'][0]['url'].replace('_thumb', '_original')}"
                            )
                        except KeyError as e:
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
                        except KeyError as e:
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
                        except KeyError as e:
                            pass

                        try:
                            embed.set_author(
                                name=bot_name,
                                url=bot_url,
                                icon_url=repl_avatar
                            )
                        except KeyError as e:
                            pass

                        embed.set_footer(
                            text='Data provided by IGDB',
                            icon_url='https://www.igdb.com/favicon-196x196.png'
                        )

                        message = await channel.send(embed=embed)
                        thread = await message.create_thread(name=embed.title)

    # Start the server
    keep_alive.keep_alive()

    # Login the bot
    bot.run(bot_token)


if __name__ == '__main__':
    main()
