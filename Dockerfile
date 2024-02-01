# syntax=docker/dockerfile:1.4
# artifacts: false
# platforms: linux/amd64
FROM python:3.13.0a3-slim-bullseye

# Basic config
ARG DAILY_TASKS=true
ARG DAILY_RELEASES=true
ARG DAILY_TASKS_UTC_HOUR=12

# Secret config
ARG BOT_TOKEN
ARG DAILY_CHANNEL_ID
ARG GRAVATAR_EMAIL
ARG IGDB_CLIENT_ID
ARG IGDB_CLIENT_SECRET

# Environment variables
ENV DAILY_TASKS=$DAILY_TASKS
ENV DAILY_RELEASES=$DAILY_RELEASES
ENV DAILY_CHANNEL_ID=$DAILY_CHANNEL_ID
ENV DAILY_TASKS_UTC_HOUR=$DAILY_TASKS_UTC_HOUR
ENV BOT_TOKEN=$BOT_TOKEN
ENV GRAVATAR_EMAIL=$GRAVATAR_EMAIL
ENV IGDB_CLIENT_ID=$IGDB_CLIENT_ID
ENV IGDB_CLIENT_SECRET=$IGDB_CLIENT_SECRET

WORKDIR /app/

COPY requirements.txt .
COPY *.py .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "discord_bot.py"]
