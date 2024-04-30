# support-bot
[![GitHub Workflow Status (CI)](https://img.shields.io/github/actions/workflow/status/lizardbyte/support-bot/ci.yml.svg?branch=master&label=CI%20build&logo=github&style=for-the-badge)](https://github.com/LizardByte/support-bot/actions/workflows/ci.yml?query=branch%3Amaster)
[![Codecov](https://img.shields.io/codecov/c/gh/LizardByte/support-bot.svg?token=900Q93P1DE&style=for-the-badge&logo=codecov&label=codecov)](https://app.codecov.io/gh/LizardByte/support-bot)

Support bot written in python to help manage LizardByte communities. The current focus is discord and reddit, but other
platforms such as GitHub discussions/issues could be added.


## Overview

### Discord Slash Commands

| command  | description                                              |
|----------|----------------------------------------------------------|
| /help    | Return help message, for a list of all possible commands |


## Instructions

### Discord

* Setup an application at [discord developer portal](https://discord.com/developers/applications).
* On `Bot` page enabled these:
  * Presence Intent
  * Server Members Intent
  * Copy the `Token`
* Add the following as environment variables or in a `.env` file (use `sample.env` as an example).  
  :exclamation: if using Docker these can be arguments.  
  :warning: Never publicly expose your tokens, secrets, or ids.  

| variable                | required | default                                              | description                                                   |
|-------------------------|----------|------------------------------------------------------|---------------------------------------------------------------|
| DISCORD_BOT_TOKEN       | True     | `None`                                               | Token from Bot page on discord developer portal.              |
| DAILY_TASKS             | False    | `true`                                               | Daily tasks on or off.                                        |
| DAILY_RELEASES          | False    | `true`                                               | Send a message for each game released on this day in history. |
| DAILY_CHANNEL_ID        | False    | `None`                                               | Required if daily_tasks is enabled.                           |
| DAILY_TASKS_UTC_HOUR    | False    | `12`                                                 | The hour to run daily tasks.                                  |
| GRAVATAR_EMAIL          | False    | `None`                                               | Gravatar email address for bot avatar.                        |
| IGDB_CLIENT_ID          | False    | `None`                                               | Required if daily_releases is enabled.                        |
| IGDB_CLIENT_SECRET      | False    | `None`                                               | Required if daily_releases is enabled.                        |
| SUPPORT_COMMANDS_REPO   | False    | `https://github.com/LizardByte/support-bot-commands` | Repository for support commands.                              |
| SUPPORT_COMMANDS_BRANCH | False    | `master`                                             | Branch for support commands.                                  |

* Running bot:
  * `python -m src`
* Invite bot to server:
  * `https://discord.com/api/oauth2/authorize?client_id=<the client id of the bot>&permissions=8&scope=bot%20applications.commands`


### Reddit

* Set up an application at [reddit apps](https://www.reddit.com/prefs/apps/).
  * The redirect uri should be https://localhost:8080
  * Take note of the `client_id` and `client_secret`
* Enter the following as environment variables  

  | Parameter          | Required | Default | Description                                                             |
  |--------------------|----------|---------|-------------------------------------------------------------------------|
  | PRAW_CLIENT_ID     | True     | None    | `client_id` from reddit app setup page.                                 |
  | PRAW_CLIENT_SECRET | True     | None    | `client_secret` from reddit app setup page.                             |
  | PRAW_SUBREDDIT     | True     | None    | Subreddit to monitor (reddit user should be moderator of the subreddit) |
  | DISCORD_WEBHOOK    | False    | None    | URL of webhook to send discord notifications to                         |
  | GRAVATAR_EMAIL     | False    | None    | Gravatar email address to get avatar from                               |
  | REDDIT_USERNAME    | True     | None    | Reddit username                                                         |
* | REDDIT_PASSWORD    | True     | None    | Reddit password                                                         |

* Running bot:
  * `python -m src`
