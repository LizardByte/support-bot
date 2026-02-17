# support-bot
[![GitHub Workflow Status (CI)](https://img.shields.io/github/actions/workflow/status/lizardbyte/support-bot/ci.yml.svg?branch=master&label=CI%20build&logo=github&style=for-the-badge)](https://github.com/LizardByte/support-bot/actions/workflows/ci.yml?query=branch%3Amaster)
[![Codecov](https://img.shields.io/codecov/c/gh/LizardByte/support-bot.svg?token=900Q93P1DE&style=for-the-badge&logo=codecov&label=codecov)](https://app.codecov.io/gh/LizardByte/support-bot)

Support bot written in python to help manage LizardByte communities. The current focus is Discord and Reddit, but other
platforms such as GitHub discussions/issues might be added in the future.


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

### Reddit

* Set up an application at [reddit apps](https://www.reddit.com/prefs/apps/).
  * The redirect uri should be https://localhost:8080
  * Take note of the `client_id` and `client_secret`

### Environment Variables

* Add the following as environment variables or in a `.env` file (use `sample.env` as an example).

> [!TIP]
> If using Docker, these can be arguments.

> [!WARNING]
> Never publicly expose your tokens, secrets, or ids.

| variable                         | required | default                                              | description                                                                                |
|----------------------------------|----------|------------------------------------------------------|--------------------------------------------------------------------------------------------|
| DATA_REPO                        | False    | `https://github.com/LizardByte/support-bot-data`     | Repository to store persistent data. This repository should be private!                    |
| DATA_REPO_BRANCH                 | False    | `master`                                             | Branch to store persistent data.                                                           |
| DISCORD_BOT_TOKEN                | True     | `None`                                               | Token from Bot page on discord developer portal.                                           |
| DISCORD_CLIENT_ID                | True     | `None`                                               | Discord OAuth2 client id.                                                                  |
| DISCORD_CLIENT_SECRET            | True     | `None`                                               | Discord OAuth2 client secret.                                                              |
| DISCORD_GITHUB_STATUS_CHANNEL_ID | True     | `None`                                               | Channel ID to send GitHub status updates to.                                               |
| DISCORD_LEVEL_UP_CHANNEL_ID      | False    | `None`                                               | Channel ID to send user level up messages to.                                              |
| DISCORD_LOG_CHANNEL_ID           | False    | `None`                                               | Channel ID to send bot log messages to. This should be a private channel.                  |
| DISCORD_REDDIT_CHANNEL_ID        | True     | `None`                                               | Channel ID to send Reddit post updates to.                                                 |
| DISCORD_REDIRECT_URI             | False    | `https://localhost:8080/discord/callback`            | The redirect uri for OAuth2. Must be publicly accessible.                                  |
| DISCORD_SPONSORS_CHANNEL_ID      | True     | `None`                                               | Channel ID to send sponsorship updates to.                                                 |
| GIT_USER_EMAIL                   | True     | `None`                                               | Email address for git commits.                                                             |
| GIT_USER_NAME                    | True     | `None`                                               | Username for git commits.                                                                  |
| GIT_TOKEN                        | True     | `None`                                               | GitHub personal access token. Must have `repo` write access. Falls back to `GITHUB_TOKEN`. |
| GITHUB_CLIENT_ID                 | True     | `None`                                               | GitHub OAuth2 client id.                                                                   |
| GITHUB_CLIENT_SECRET             | True     | `None`                                               | GitHub OAuth2 client secret.                                                               |
| GITHUB_REDIRECT_URI              | False    | `https://localhost:8080/github/callback`             | The redirect uri for OAuth2. Must be publicly accessible.                                  |
| GITHUB_TOKEN                     | True     | `None`                                               | GitHub personal access token. Must have `read:org`                                         |
| GITHUB_WEBHOOK_SECRET_KEY        | True     | `None`                                               | A secret value to ensure webhooks are from trusted sources.                                |
| GRAVATAR_EMAIL                   | False    | `None`                                               | Gravatar email address for bot avatar.                                                     |
| PRAW_CLIENT_ID                   | True     | `None`                                               | `client_id` from reddit app setup page.                                                    |
| PRAW_CLIENT_SECRET               | True     | `None`                                               | `client_secret` from reddit app setup page.                                                |
| PRAW_SUBREDDIT                   | True     | `None`                                               | Subreddit to monitor (reddit user should be moderator of the subreddit)                    |
| REDDIT_USERNAME                  | True     | `None`                                               | Reddit username                                                                            |
| REDDIT_PASSWORD                  | True     | `None`                                               | Reddit password                                                                            |
| SUPPORT_COMMANDS_REPO            | False    | `https://github.com/LizardByte/support-bot-commands` | Repository for support commands.                                                           |
| SUPPORT_COMMANDS_BRANCH          | False    | `master`                                             | Branch for support commands.                                                               |

### Install

Install the project and its dependencies:

```bash
python -m pip install -e .
```

For development (includes test dependencies):

```bash
python -m pip install -e ".[dev]"
```

### Start

```bash
python -m src
```

* Invite bot to server:
  * `https://discord.com/api/oauth2/authorize?client_id=<the client id of the bot>&permissions=8&scope=bot%20applications.commands`
