# Docker

## Using docker run
Create and run the container (substitute your `<values>`):

```bash
docker run -d \
  --name=retroarcher-discord-bot \
  --restart=unless-stopped \
  -e BOT_TOKEN=<BOT_TOKEN> \
  -e DAILY_CHANNEL_ID=<DAILY_CHANNEL_ID> \
  -e DAILY_RELEASES=<DAILY_RELEASES> \
  -e DAILY_TASKS=<DAILY_TASKS> \
  -e DAILY_TASKS_UTC_HOUR=<DAILY_TASKS_UTC_HOUR> \
  -e GRAVATAR_EMAIL=<GRAVATAR_EMAIL> \
  -e IGDB_CLIENT_ID=<IGDB_CLIENT_ID> \
  -e IGDB_CLIENT_SECRET=<IGDB_CLIENT_SECRET> \
  retroarcher/discord-bot
```

To update the container it must be removed and recreated:

```bash
# Stop the container
docker stop retroarcher-discord-bot
# Remove the container
docker rm retroarcher-discord-bot
# Pull the latest update
docker pull retroarcher/discord-bot
# Run the container with the same parameters as before
docker run -d ...
```

## Using docker-compose

Create a `docker-compose.yml` file with the following contents (substitute your `<values>`):

```yaml
version: '3'
services:
  retroarcher-discord-bot:
    image: retroarcher/discord-bot
    container_name: retroarcher-discord-bot
    restart: unless-stopped
    environment:
      - BOT_TOKEN=<BOT_TOKEN>
      - DAILY_CHANNEL_ID=<DAILY_CHANNEL_ID>
      - DAILY_RELEASES=<DAILY_RELEASES>
      - DAILY_TASKS=<DAILY_TASKS>
      - DAILY_TASKS_UTC_HOUR=<DAILY_TASKS_UTC_HOUR>
      - GRAVATAR_EMAIL=<GRAVATAR_EMAIL>
      - IGDB_CLIENT_ID=<IGDB_CLIENT_ID>
      - IGDB_CLIENT_SECRET=<IGDB_CLIENT_SECRET>
```

Create and start the container (run the command from the same folder as your `docker-compose.yml` file):

```bash
docker-compose up -d
```

To update the container:
```bash
# Pull the latest update
docker-compose pull
# Update and restart the container
docker-compose up -d
```

## Parameters
You must substitute the `<values>` with your own settings.

| Parameter            | Required | Default | Description                                                   |
| -------------------- | -------- | ------- | ------------------------------------------------------------- |
| BOT_TOKEN            | True     | None    | Token from Bot page on discord developer portal.              |
| DAILY_TASKS          | False    | true    | Daily tasks on or off.                                        |
| DAILY_RELEASES       | False    | true    | Send a message for each game released on this day in history. |
| DAILY_CHANNEL_ID     | False    | None    | Required if daily_tasks is enabled.                           |
| DAILY_TASKS_UTC_HOUR | False    | 12      | The hour to run daily tasks.                                  |
| GRAVATAR_EMAIL       | False    | None    | Gravatar email address for bot avatar.                        |
| IGDB_CLIENT_ID       | False    | None    | Required if daily_releases is enabled.                        |
| IGDB_CLIENT_SECRET   | False    | None    | Required if daily_releases is enabled.                        |
