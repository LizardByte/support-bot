# RetroArcher.discord-bot
Discord bot written in python to help manage the RetroArcher discord server.


## Overview
This is a custom discord bot with some slash commands to help with support on the RetroArcher discord server.

| command | argument 1 | argument 2 | description                      |
| ------- | ---------- | ---------- | -------------------------------- |
| /donate | user       |            | Return donation links            |
| /random |            |            | Return a random video game quote |
| /wiki   | page       | user       | Return the specified wiki page   |



## Instructions
* Setup an application at [discord developer portal](https://discord.com/developers/applications).
* On `Bot` page enabled these:
  * Presence Intent
  * Server Members Intent
  * Copy the `Token`
* Enter the following into the repl secrets or in a `.env` file (use `sample.env` as an example).  
  :warning: Never publicly expose your tokens, secrets, or ids.

  | variable             | required | default | description                                                   |
  | -------------------- | -------- | ------- | ------------------------------------------------------------- |
  | bot_token            | True     | None    | Token from Bot page on discord developer portal.              |
  | daily_tasks          | False    | true    | Daily tasks on or off.                                        |
  | daily_releases       | False    | true    | Send a message for each game released on this day in history. |
  | daily_channel_id     | False    | None    | Required if daily_tasks is enabled.                           |
  | daily_tasks_utc_hour | False    | 12      | The hour to run daily tasks.                                  |
  | igdb_client_id       | False    | None    | Required if daily_releases is enabled.                        |
  | igdb_client_secret   | False    | None    | Required if daily_releases is enabled.                        |
  | REPL_SLUG            | False    | None    | Fake this when running locally. Value doesn't matter.         |
  | REPL_OWNER           | False    | None    | Fake this when running locally. Value should be username.     |

* Running bot:
  * `python discord_bot.py`
* Invite bot to server:
  * `https://discord.com/api/oauth2/authorize?client_id=<the client id of the bot>&permissions=8&scope=bot%20applications.commands`


## To Do:
Initial functions to add
- [x] Slash commands to return wiki pages
- [x] Donate command
- [ ] Parse github wiki markdown and make friendly for discord embeds

Maybe later on add these type of tasks
- [ ] Count/track user interaction... rank users
- [ ] Moderate the discord
- [ ] Search/Lookup games on IGDB
