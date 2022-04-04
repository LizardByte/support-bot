FROM python:3.9.12-bullseye-slim

# Basic config
ARG daily_tasks=true
ARG daily_releases=true
ARG daily_tasks_utc_hour=12

# Secret config
ARG bot_token
ARG daily_channel_id
ARG gravatar_email
ARG igdb_client_id
ARG igdb_client_secret

# Environment variables
ENV daily_tasks=$DAILY_TASKS
ENV daily_releases=$DAILY_RELEASES
ENV daily_channel_id=$DAILY_CHANNEL_ID
ENV daily_tasks_utc_hour=$DAILY_TASKS_UTC_HOUR
ENV bot_token=$BOT_TOKEN
ENV gravatar_email=$GRAVATAR_EMAIL
ENV igdb_client_id=$IGDB_CLIENT_ID
ENV igdb_client_secret=$IGDB_CLIENT_SECRET

COPY requirements.txt .
COPY *.py .
COPY commands.json .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "discord_bot.py"]
