import discord
from discord.ext import commands
from discord_slash import SlashCommand
from discord_slash.utils.manage_commands import create_option, create_choice
import json
import os
import re
import requests
import sys
import urllib

# local imports
import keep_alive


def get_repl_avatar(user_name):
    url = f'https://replit.com/@{user_name}'
    repl_page = requests.get(url)

    image_link = re.search(r'property=\"og:image\" content=\"(https://storage\.googleapis\.com/replit/images/[a-z_0-9]*\.png)\"', repl_page.text).group(1)

    return image_link


def main():
    # constants
    bot_token = os.environ['bot_token']
    client = commands.Bot(command_prefix="/", intents=discord.Intents.all())
    slash = SlashCommand(client, sync_commands=True)

    botName = os.environ['REPL_SLUG']
    botUrl = 'https://github.com/RetroArcher'

    # replit avatar
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
        print('Error: %s not found' % (command_file))
        sys.exit(1)


    # functions
    def convert_wiki(gitUser, gitRepo, wikiFile):
        url = 'https://raw.githubusercontent.com/wiki/%s/%s/%s.md' % (gitUser, gitRepo, wikiFile)
        f = requests.get(url)

        return f.text


    def discordMessage(gitUser, gitRepo, wikiFile, color):
        url = 'https://github.com/%s/%s/wiki/%s' % (gitUser, gitRepo, wikiFile)
        embed_message = convert_wiki(gitUser, gitRepo, wikiFile)
        if len(embed_message) > 2048:
            seeMore = '...\n\n...See More on [Github](%s)' % (url)
            embed_message = '%s%s' % (embed_message[:2048 - len(seeMore)], seeMore)
        return url, embed_message, color


    # on ready
    @client.event
    async def on_ready():
        print('Logged in as')
        print(client.user.name)
        print(client.user.id)
        print(discord.__version__)
        print('------')

        print('Servers connected to:')
        print(client.guilds)
        guild_ids = []
        for guild in client.guilds:
            print(guild.name)
            #print(guild.id)
            guild_ids.append(guild.id)
            #print(guild_ids)
        with open(guild_file, 'w') as f:
            json.dump(guild_ids, f, indent=2)

        print("Conected to %s!" % (os.environ['REPL_SLUG']))
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="the RetroArcher server"))


    # Donate command
    @slash.slash(name="donate",
                description="Support the development of RetroArcher",
                options=[
                    create_option(
                        name='user',
                        description='Enter the username to mention',
                        option_type=6,
                        required=True
                        )
                    ],
                guild_ids=guild_ids
                )
    async def donate(ctx, user: discord.Member = None):
        embeds = []
        embeds.append(discord.Embed(color=0x333))
        embeds[-1].set_author(name='Github Sponsors', url='https://github.com/sponsors/ReenigneArcher', icon_url='https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png')

        embeds.append(discord.Embed(color=0xf96854))
        embeds[-1].set_author(name='Patreon', url='https://www.patreon.com/RetroArcher', icon_url='https://th.bing.com/th/id/OIP.suF0Aufc2rX2gzgPB2mXpAHaHa?pid=ImgDet&rs=1')

        embeds.append(discord.Embed(color=0x003087))
        embeds[-1].set_author(name='PayPal', url='https://paypal.me/ReenigneArcher', icon_url='https://img.etimg.com/thumb/msid-60762134,width-300,imgsize-9757,resizemode-4/paypal-reduces-remittance-certificate-charges-by-50-for-small-sellers.jpg')

        if user:
            await ctx.send('Thank you for your support %s!' % (user.mention), embeds=embeds)
        else:
            await ctx.send('Thank you for your support!', embeds=embeds)


    # Combine all wiki pages into one slash command with options/choices
    # Wiki Command
    wiki_choices = []
    for key, value in command_dict.items():
        description = value.replace('-', ' ').replace('_', ' ').strip()
        wiki_choices.append(create_choice(name=key, value=key))

    @slash.slash(name="wiki",
                description="Return any of the listed Wiki pages as a message.",
                options=[
                    create_option(
                        name='page',
                        description='Return the selected Wiki page as a message',
                        option_type=3,
                        required=True,
                        choices=wiki_choices
                        ),
                    create_option(
                        name='user',
                        description='Enter the username to mention',
                        option_type=6,
                        required=False
                        )
                    ],
                guild_ids=guild_ids
                )

    async def wiki(ctx, page: str, user: discord.Member = None):
        v = command_dict[page]
        print(user)

        gitUser = 'RetroArcher'
        gitRepo = 'RetroArcher.bundle'
        wikiFile = urllib.parse.quote(v)
        title = v.replace('-', ' ').replace('_', ' ').strip()
        color=0xE5A00D

        url, embed_message, color = discordMessage(gitUser, gitRepo, wikiFile, color)
        embed = discord.Embed(title=title, url=url, description=embed_message, color=color)
        embed.set_author(name=botName, url=botUrl, icon_url=repl_avatar)

        if user:
            await ctx.send(user.mention, embed=embed)
        else:
            await ctx.send(embed=embed)


    # Start the server
    keep_alive.keep_alive()

    # Login the bot
    client.run(bot_token)

if __name__ == '__main__':
    main()
