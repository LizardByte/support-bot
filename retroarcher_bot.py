import discord
from discord.ext import commands
from discord_slash import SlashCommand
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
# on message
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

# context reference
# https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.ext.commands.Context

# Commands
for key, value in command_dict.items():
    description = value.replace('-', ' ').replace('_', ' ').strip()
    @slash.slash(name=key, description=description, guild_ids=guild_ids)
    async def _ping(ctx):
        for k, v in command_dict.items():
            if ctx.command == k:
                gitUser = 'RetroArcher'
                gitRepo = 'RetroArcher.bundle'
                wikiFile = urllib.parse.quote(v)
                title = v.replace('-', ' ').replace('_', ' ').strip()
                color=0xE5A00D

                url, embed_message, color = discordMessage(gitUser, gitRepo, wikiFile, color)
                embed = discord.Embed(title=title, url=url, description=embed_message, color=color)
                embed.set_author(name=botName, url=botUrl, icon_url=iconUrl)

                await ctx.send(embed=embed)
                break


@slash.slash(name="donate", description="donate", guild_ids=guild_ids)
async def _ping(ctx): 
        embed = discord.Embed(title="Donate", color=0xE5A00D)
        embed.add_field(name="Github", value="[Link](https://github.com/sponsors/ReenigneArcher)", inline=False)
        embed.add_field(name="Patreon", value="[Link](https://www.patreon.com/RetroArcher)", inline=False)
        embed.add_field(name="PayPal", value="[Link](https://paypal.me/ReenigneArcher)", inline=False)
        await ctx.send(embed=embed)


# Start the server
keep_alive.keep_alive()

# Login the bot
client.run(bot_token)
