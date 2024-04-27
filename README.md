# support-bot
[![GitHub Workflow Status (CI)](https://img.shields.io/github/actions/workflow/status/lizardbyte/support-bot/ci.yml.svg?branch=master&label=CI%20build&logo=github&style=for-the-badge)](https://github.com/LizardByte/support-bot/actions/workflows/ci.yml?query=branch%3Amaster)
[![Codecov](https://img.shields.io/codecov/c/gh/LizardByte/support-bot.svg?token=900Q93P1DE&style=for-the-badge&logo=codecov&label=codecov)](https://app.codecov.io/gh/LizardByte/support-bot)

Support bot written in python to help manage LizardByte communities. The current focus is discord and reddit, but other
platforms such as GitHub discussions/issues could be added.


## Overview

### Discord Slash Commands

| command  | description                                       | argument 1          |
|----------|---------------------------------------------------|---------------------|
| /help    | Return help message                               |                     |
| /channel | Suggest to move discussion to a different channel | recommended_channel |
| /docs    | Return the specified docs page                    | user                |
| /donate  | Return donation links                             | user                |
| /random  | Return a random video game quote                  |                     |


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

| variable             | required | default | description                                                   |
|----------------------|----------|---------|---------------------------------------------------------------|
| DISCORD_BOT_TOKEN    | True     | None    | Token from Bot page on discord developer portal.              |
| DAILY_TASKS          | False    | true    | Daily tasks on or off.                                        |
| DAILY_RELEASES       | False    | true    | Send a message for each game released on this day in history. |
| DAILY_CHANNEL_ID     | False    | None    | Required if daily_tasks is enabled.                           |
| DAILY_TASKS_UTC_HOUR | False    | 12      | The hour to run daily tasks.                                  |
| GRAVATAR_EMAIL       | False    | None    | Gravatar email address for bot avatar.                        |
| IGDB_CLIENT_ID       | False    | None    | Required if daily_releases is enabled.                        |
| IGDB_CLIENT_SECRET   | False    | None    | Required if daily_releases is enabled.                        |

* Running bot:
  * `python -m src`
* Invite bot to server:
  * `https://discord.com/api/oauth2/authorize?client_id=<the client id of the bot>&permissions=8&scope=bot%20applications.commands`


### Reddit

* Set up an application at [reddit apps](https://www.reddit.com/prefs/apps/).
  * The redirect uri must be publicly accessible.
    * If using Replit, enter `https://<REPL_SLUG>.<REPL_OWNER>.repl.co`
    * Otherwise, it is recommended to use [Nginx Proxy Manager](https://nginxproxymanager.com/) and [Duck DNS](https://www.duckdns.org/)
  * Take note of the `client_id` and `client_secret`
* Enter the following as environment variables  

  | Parameter          | Required | Default | Description                                                             |
  |--------------------|----------|---------|-------------------------------------------------------------------------|
  | PRAW_CLIENT_ID     | True     | None    | `client_id` from reddit app setup page.                                 |
  | PRAW_CLIENT_SECRET | True     | None    | `client_secret` from reddit app setup page.                             |
  | PRAW_SUBREDDIT     | True     | None    | Subreddit to monitor (reddit user should be moderator of the subreddit) |
  | DISCORD_WEBHOOK    | False    | None    | URL of webhook to send discord notifications to                         |
  | GRAVATAR_EMAIL     | False    | None    | Gravatar email address to get avatar from                               |
  | REDIRECT_URI       | True     | None    | The redirect URI entered during the reddit application setup            |

* First run (or manually get a new refresh token):
  * Delete `./data/refresh_token` file if needed
  * `python -m src`
  * Open browser and login to reddit account to use with bot
  * Navigate to URL printed in console and accept
  * `./data/refresh_token` file is written
* Running after refresh_token already obtained:
  * `python -m src`
