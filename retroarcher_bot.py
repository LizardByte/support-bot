import discord
from discord.ext import commands
from discord_slash import SlashCommand
from discord_slash.utils.manage_commands import create_option, create_choice
import os
import requests
import urllib


# local imports
import keep_alive


# constants
bot_token = os.environ['bot_token']
client = commands.Bot(command_prefix="/", intents=discord.Intents.all())
slash = SlashCommand(client, sync_commands=True)

guild_ids = [int(os.environ['server_id'])]

botName = 'RetroArcher bot'
botUrl = 'https://github.com/RetroArcher'
iconUrl = 'https://raw.githubusercontent.com/RetroArcher/RetroArcher.branding/main/logos/RetroArcher-white-256x256.png'


# context reference
# https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.ext.commands.Context


# command : wiki-file
command_dict = {
    'home' : 'Home',
    'wiki' : '_Sidebar',
    'logs' : 'Log-Files',
    'server' : 'Prerequisites,-Server',
    'client' : 'Prerequisites,-Client',
    'clients' : 'Supported-clients',
    'install' : 'Installation',
    'python' : 'Install-Python',
    'tautulli' : 'Configure-Tautulli',
    'gamestreaming' : 'Configure-Game-Streaming',
    'settings' : 'Configure-RetroArcher',
    'platforms' : 'Platform-Names',
    'scan' : 'Scanning-Games-and-Roms',
    'library' : 'Configure-Game-Library',
    'config_client' : 'Configure-Clients',
    'meta-igdb' : 'Metadata-(IGDB)',
    'meta-local' : 'Metadata-(Local)',
    'config_retroarch' : 'Configure-RetroArch',
    'cores_retroarch' : 'Default-Cores',
    'gamepads_retroarch' : 'Game-pads',
    'config_cemu' : 'Configure-CEMU',
    'config_rpcs3' : 'Configure-RPCS3',
    'todo' : 'To-Do',
}


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
    print("Conected to RetroArcher bot!")
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="the RetroArcher server"))

'''
# on message, no slash command created
@client.event
async def on_message(message):
    print(message)
    print(message.content)
    if message.author == client.user:
        return #don't do anything if author is this bot
    
    print(message.content)

    for key, value in command_dict.items():
        if message.content == '!%s' % (key):
            gitUser = 'RetroArcher'
            gitRepo = 'RetroArcher.bundle'
            wikiFile = urllib.parse.quote(value)
            title = value.replace('-', ' ').replace('_', ' ').strip()
            color=0xE5A00D

            url, embed_message, color = discordMessage(gitUser, gitRepo, wikiFile, color)
            embed = discord.Embed(title=title, url=url, description=embed_message, color=color)
            embed.set_author(name=botName, url=botUrl, icon_url=iconUrl)

            await message.channel.send(embed=embed)
            break
'''

'''
# slash command for each wiki page in dictionary
# Commands
for key, value in command_dict.items():
    description = value.replace('-', ' ').replace('_', ' ').strip()
    @slash.slash(name=key, description=description, guild_ids=guild_ids)
    async def _ping(ctx):
        v = command_dict[ctx.command]
        gitUser = 'RetroArcher'
        gitRepo = 'RetroArcher.bundle'
        wikiFile = urllib.parse.quote(v)
        title = v.replace('-', ' ').replace('_', ' ').strip()
        color=0xE5A00D

        url, embed_message, color = discordMessage(gitUser, gitRepo, wikiFile, color)
        embed = discord.Embed(title=title, url=url, description=embed_message, color=color)
        embed.set_author(name=botName, url=botUrl, icon_url=iconUrl)

        await ctx.send(embed=embed)
'''


# Donate command... let's improve this
@slash.slash(name="donate_old", description="donate", guild_ids=guild_ids)
async def _ping(ctx):
    embed = discord.Embed(title="Donate", color=0xE5A00D)
    embed.add_field(name="Github", value="[Link](https://github.com/sponsors/ReenigneArcher)", inline=False)
    embed.add_field(name="Patreon", value="[Link](https://www.patreon.com/RetroArcher)", inline=False)
    embed.add_field(name="PayPal", value="[Link](https://paypal.me/ReenigneArcher)", inline=False)
    await ctx.send(embed=embed)


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
    embed.set_author(name=botName, url=botUrl, icon_url=iconUrl)

    if user:
        await ctx.send(user.mention, embed=embed)
    else:
        await ctx.send(embed=embed)
        


# Start the server
keep_alive.keep_alive()

# Login the bot
client.run(bot_token)
