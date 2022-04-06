# RetroArcher.discord-bot
Discord bot written in python to help manage the RetroArcher discord server.


## Overview
This is a custom discord bot with some slash commands to help with support on the RetroArcher discord server.

| command | argument 1 | argument 2 | description                      |
| ------- | ---------- | ---------- | -------------------------------- |
| /help   |            |            | Return help message              |
| /donate | user       |            | Return donation links            |
| /random |            |            | Return a random video game quote |
| /wiki   | page       | user       | Return the specified wiki page   |



## Instructions
* Setup an application at [discord developer portal](https://discord.com/developers/applications).
* On `Bot` page enabled these:
  * Presence Intent
  * Server Members Intent
  * Copy the `Token`
* Add the following as environment variables or in a `.env` file (use `sample.env` as an example).  
  :exclamation: if using Docker these can be arguments.  
  :warning: Never publicly expose your tokens, secrets, or ids.  

  | variable             | required | default | description                                                   |
  | -------------------- | -------- | ------- | ------------------------------------------------------------- |
  | BOT_TOKEN            | True     | None    | Token from Bot page on discord developer portal.              |
  | DAILY_TASKS          | False    | true    | Daily tasks on or off.                                        |
  | DAILY_RELEASES       | False    | true    | Send a message for each game released on this day in history. |
  | DAILY_CHANNEL_ID     | False    | None    | Required if daily_tasks is enabled.                           |
  | DAILY_TASKS_UTC_HOUR | False    | 12      | The hour to run daily tasks.                                  |
  | GRAVATAR_EMAIL       | False    | None    | Gravatar email address for bot avatar.                        |
  | IGDB_CLIENT_ID       | False    | None    | Required if daily_releases is enabled.                        |
  | IGDB_CLIENT_SECRET   | False    | None    | Required if daily_releases is enabled.                        |

* Running bot:
  * `python discord_bot.py`
* Invite bot to server:
  * `https://discord.com/api/oauth2/authorize?client_id=<the client id of the bot>&permissions=8&scope=bot%20applications.commands`
