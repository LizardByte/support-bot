# RetroArcher.discord-bot
Discord bot written in python to help manage the RetroArcher discord server.


## Overview
This is a custom discord bot wish some slash commands to help with support on the RetroArcher discord server.

| command | argument 1 | argument 2 |
| ------- | ---------- | ---------- |
| /wiki   | page       | user       |
| /donate | user       |            |


## Instructions
* Setup an application at [discord developer portal](https://discord.com/developers/applications).
* On `OAuth2` page, copy the client secret
* On `Bot` page enabled these:
  * Presence Intent
  * Server Members Intent
* Enter the following into the repl secrets
  * bot_token = `client_secret` from discord app setup page
  * server_id = right click server in discord, `copy id`
* Running bot:
  * `python discord_bot.py`


## To Do:
Initial functions to add
- [x] Slash commands to return wiki pages
- [x] Donate command
- [ ] Parse github wiki markdown and make friendly for discord embeds

Maybe later on add these type of tasks
- [ ] Count/track user interaction... rank users
- [ ] Moderate the discord
- [ ] Search/Lookup games on IGDB
