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

# development imports
from dotenv import load_dotenv
load_dotenv()


def get_repl_avatar(user_name):
    url = f'https://replit.com/@{user_name}'
    repl_page = requests.get(url)

    image_link = re.search(
        r'property=\"og:image\" content=\"(https://storage\.googleapis\.com/replit/images/[a-z_0-9]*\.png)\"',
        repl_page.text
    ).group(1)

    return image_link


def main():
    # constants
    bot_token = os.environ['bot_token']
    client = commands.Bot(command_prefix="/", intents=discord.Intents.all())
    slash = SlashCommand(client, sync_commands=True)

    bot_name = os.environ['REPL_SLUG']
    bot_url = 'https://github.com/RetroArcher'

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
        print('Error: %s not found' % command_file)
        sys.exit(1)

    # functions
    def convert_wiki(git_user, git_repo, wiki_file):
        url = 'https://raw.githubusercontent.com/wiki/%s/%s/%s.md' % (git_user, git_repo, wiki_file)
        response = requests.get(url)

        return response.text

    def discord_message(git_user, git_repo, wiki_file, color):
        url = 'https://github.com/%s/%s/wiki/%s' % (git_user, git_repo, wiki_file)
        embed_message = convert_wiki(git_user, git_repo, wiki_file)
        if len(embed_message) > 2048:
            see_more = '...\n\n...See More on [Github](%s)' % url
            embed_message = '%s%s' % (embed_message[:2048 - len(see_more)], see_more)
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
            guild_ids.append(guild.id)
        with open(guild_file, 'w') as file:
            json.dump(guild_ids, file, indent=2)

        print("Connected to %s!" % (os.environ['REPL_SLUG']))
        await client.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the RetroArcher server"
            )
        )

    # Donate command
    @slash.slash(name="donate",
                 description="Support the development of RetroArcher",
                 options=[
                     create_option(name='user',
                                   description='Enter the username to mention',
                                   option_type=6,
                                   required=True
                                   )
                 ],
                 guild_ids=guild_ids
                 )
    async def donate(ctx, user: discord.Member = None):
        embeds = [discord.Embed(color=0x333)]
        embeds[-1].set_author(name='Github Sponsors',
                              url='https://github.com/sponsors/ReenigneArcher',
                              icon_url='https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
                              )

        embeds.append(discord.Embed(color=0xf96854))
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
            await ctx.send(f'Thank you for your support {user.mention}!', embeds=embeds)
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
                     create_option(name='page',
                                   description='Return the selected Wiki page as a message',
                                   option_type=3,
                                   required=True,
                                   choices=wiki_choices
                                   ),
                     create_option(name='user',
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

        git_user = 'RetroArcher'
        git_repo = 'RetroArcher.bundle'
        wiki_file = urllib.parse.quote(v)
        title = v.replace('-', ' ').replace('_', ' ').strip()
        color = 0xE5A00D

        url, embed_message, color = discord_message(git_user, git_repo, wiki_file, color)
        embed = discord.Embed(title=title, url=url, description=embed_message, color=color)
        embed.set_author(name=bot_name, url=bot_url, icon_url=repl_avatar)

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
