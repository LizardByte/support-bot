## Overview
This is a custom discord bot wish some slash commands to help with support on the RetroArcher discord server.

| command | argument 1 | argument 2 |
| ------- | ---------- | ---------- |
| /wiki   | page       | user       |
| /donate | user       |            |

## Forking
The bot is setup and running in [replit](https://replit.com/@ReenigneArcher/RetroArcherdiscord-bot) and can be easily forked and modified.

Required environment variables:
* bot_token = client secret from Apps OAuth2 page on Discord Developer Portal 
* server_id = server/guild id... right click server in discord, copy id

## Planned Enhancements
To do:
- [ ] parse markdown from github wiki pages and return in discord embed friendly format
  * some things do not carry over like comments are visible, tables are ugly, headings
- [ ] move wiki pages dictionary to a separate json file and import it using json module
  * will allow bot to re-read required wiki pages without the need to shutdown the bot
- [ ] put wiki pages command on a timed loop to re-read json every couple of minutes (5 minutes?)
