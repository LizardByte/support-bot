import discord
from discord_slash import SlashCommand
import os
import requests
import urllib

# local imports
import keep_alive

def convert_wiki(gitUser, gitRepo, wikiFile):
    url = 'https://raw.githubusercontent.com/wiki/%s/%s/%s.md' % (gitUser, gitRepo, wikiFile)
    f = requests.get(url)
    return f.text


def discordMessage(gitUser, gitRepo, wikiFile, color):
    url = 'https://github.com/%s/%s/wiki/%s' % (gitUser, gitRepo, wikiFile)
    message = convert_wiki(gitUser, gitRepo, wikiFile)
    if len(message) > 2048:
        seeMore = '...\n\n...See More on [Github](%s)' % (url)
        message = '%s%s' % (message[:2048 - len(seeMore)], seeMore)
    return url, message, color


# constants
bot_token = os.environ['bot_token']
client = discord.Client(intents=discord.Intents.all())
slash = SlashCommand(client, sync_commands=True)

guild_ids = [int(os.environ['server_id'])]

botName = 'RetroArcher bot'
botUrl = 'https://github.com/RetroArcher'
iconUrl = 'https://raw.githubusercontent.com/RetroArcher/RetroArcher.branding/main/logos/RetroArcher-white-256x256.png'

# command : wiki-file
commands = {
    'home' : 'Home',
    'wiki' : '_Sidebar',
    'logs' : 'Log-Files',
    'server' : 'Prerequisites,-Server',
    'client' : 'Prerequisites,-Client',
    'clients' : 'Supported-Clients',
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
}

@client.event
async def on_ready():
    print("Conected to RetroArcher bot!")
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="the RetroArcher server"))

    

# Commands
for key, value in commands.items():
    description = value.replace('-', ' ').replace('_', ' ').strip()
    @slash.slash(name=key, description="Wiki Home", guild_ids=guild_ids)
    async def _ping(ctx): 
        gitUser = 'RetroArcher'
        gitRepo = 'RetroArcher.bundle'
        wikiFile = urllib.parse.quote(value)
        title = description
        color=0xE5A00D

        url, message, color = discordMessage(gitUser, gitRepo, wikiFile, color)
        embedVar = discord.Embed(title=title, url=url, description=message, color=color)
        embedVar.set_author(name=botName, url=botUrl, icon_url=iconUrl)

        await ctx.send(embed=embedVar)


@slash.slash(name="donate", description="donate", guild_ids=guild_ids)
async def _ping(ctx): 
        embedVar = discord.Embed(title="Donate", color=0xE5A00D)
        embedVar.add_field(name="Github", value="[Link](https://github.com/sponsors/ReenigneArcher)", inline=False)
        embedVar.add_field(name="Patreon", value="[Link](https://www.patreon.com/RetroArcher)", inline=False)
        embedVar.add_field(name="PayPal", value="[Link](https://paypal.me/ReenigneArcher)", inline=False)
        await ctx.send(embed=embedVar)


# Start the server
keep_alive.keep_alive()

# Login the bot
client.run(bot_token)
