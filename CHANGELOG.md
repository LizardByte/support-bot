# Changelog

## [0.1.3] - 2023-04-19
**Added**
- Add channel command

**Dependencies**
- Bump python-dotenv from 0.21.1 to 1.0.0
- Bump libgravatar from 1.0.3 to 1.0.4
- Bump py-cord from 2.4.0 to 2.4.1
- Bump beautifulsoup4 from 4.11.2 to 4.12.2
- Bump python from 3.11.2 to 3.11.3

**Misc**
- Update global workflows
- Update global docker
- Update docker platforms

## [0.1.2] - 2023-02-19
**Dependencies**
- Bump flask from 2.2.2 to 2.2.3
- Bump igdb-api-v4 from 0.0.5 to 0.1.0
- Bump requests from 2.28.1 to 2.28.2
- Bump python-dotenv from 0.20.0 to 0.21.1
- Bump libgravatar from 1.0.0 to 1.0.3
- Bump beautifulsoup4 from 4.11.1 to 4.11.2
- Bump py-cord from 2.0.1 to 2.4.0
- Bump python from 3.9.12 to 3.11.2

## [0.1.1] - 2022-08-20
**Changed**
- Enable timeout callback for `/docs` command after 45s
- Incomplete `/docs` commands are deleted 30s after the timeout period
- `/docs` command is reset for each call
- Fix url returned for `/docs` command when `None` was selected as category
- Move constants to `discord_constants.py`
- Move avatar related items to `discord_avatar.py`

**Added**
- Add `discord_modals.py`

**Dependencies**
- Bump flask from 2.2.1 to 2.2.2
- Bump py-cord from 2.0.0 to 2.0.1


## [0.1.0] - 2022-08-07
**Changed**
- Select Menus added to `docs` slash command to give finer control of returned documentation url
- Buttons added to `donate` slash command, removed embeds

**Removed**
- Removed guild file

**Dependencies**
- Bump flask from 2.1.3 to 2.2.1

## [0.0.5] - 2022-07-31
**Fixed**
- Bot will now self updates username and avatar
- Fixed issue with duplicate guild ids
- Random quotes are now pulled from `uno` repo

**Added**
- `docs` slash command

**Removed**
- `wiki` slash command

**Dependencies**
- Bump requests from 2.27.1 to 2.28.1
- Bump py-cord from 2.0.0b3 to 2.0.0
- Bump flask from 2.1.1 to 2.1.3

**Misc**
- Rebrand to LizardByte
- Change License to AGPL v3

## [0.0.4] - 2022-04-24
**Fixed**
- Corrected environment variable for daily release task

## [0.0.3] - 2022-04-06
**Fixed**
- Environment variable names switched to uppercase

## [0.0.2] - 2022-04-04
**Added**
- (Misc.) Workflow improvements

## [0.0.1] - 2022-04-03
**Added**
- (Misc.) Initial release

[0.0.1]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.0.1
[0.0.2]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.0.2
[0.0.3]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.0.3
[0.0.4]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.0.4
[0.0.5]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.0.5
[0.1.0]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.1.0
[0.1.1]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.1.1
[0.1.2]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.1.2
[0.1.3]: https://github.com/lizardbyte/discord-bot/releases/tag/v0.1.3
