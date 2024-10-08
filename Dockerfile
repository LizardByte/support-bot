# syntax=docker/dockerfile:1
# artifacts: false
# platforms: linux/amd64
FROM python:3.12-slim-bookworm

# CI args
ARG BRANCH
ARG BUILD_VERSION
ARG COMMIT
# note: BUILD_VERSION may be blank

ENV BRANCH=${BRANCH}
ENV BUILD_VERSION=${BUILD_VERSION}
ENV COMMIT=${COMMIT}

# Basic config
ARG DAILY_TASKS=true
ARG DAILY_RELEASES=true
ARG DAILY_TASKS_UTC_HOUR=12

# Secret config
ARG DISCORD_BOT_TOKEN
ARG DAILY_CHANNEL_ID
ARG GRAVATAR_EMAIL
ARG IGDB_CLIENT_ID
ARG IGDB_CLIENT_SECRET
ARG PRAW_CLIENT_ID
ARG PRAW_CLIENT_SECRET
ARG PRAW_SUBREDDIT
ARG DISCORD_WEBHOOK
ARG GRAVATAR_EMAIL
ARG REDIRECT_URI

# Environment variables
ENV DAILY_TASKS=$DAILY_TASKS
ENV DAILY_RELEASES=$DAILY_RELEASES
ENV DAILY_CHANNEL_ID=$DAILY_CHANNEL_ID
ENV DAILY_TASKS_UTC_HOUR=$DAILY_TASKS_UTC_HOUR
ENV DISCORD_BOT_TOKEN=$DISCORD_BOT_TOKEN
ENV GRAVATAR_EMAIL=$GRAVATAR_EMAIL
ENV IGDB_CLIENT_ID=$IGDB_CLIENT_ID
ENV IGDB_CLIENT_SECRET=$IGDB_CLIENT_SECRET
ENV PRAW_CLIENT_ID=$PRAW_CLIENT_ID
ENV PRAW_CLIENT_SECRET=$PRAW_CLIENT_SECRET
ENV PRAW_SUBREDDIT=$PRAW_SUBREDDIT
ENV DISCORD_WEBHOOK=$DISCORD_WEBHOOK
ENV GRAVATAR_EMAIL=$GRAVATAR_EMAIL
ENV REDIRECT_URI=$REDIRECT_URI

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# install dependencies
RUN <<_DEPS
#!/bin/bash
set -e
apt-get update -y
apt-get install -y --no-install-recommends \
  git
apt-get clean
rm -rf /var/lib/apt/lists/*
_DEPS

VOLUME /data

WORKDIR /app/

COPY . .
RUN <<_SETUP
#!/bin/bash
set -e

# replace the version in the code
sed -i "s/version = '0.0.0'/version = '${BUILD_VERSION}'/g" src/common.py

# install dependencies
python -m pip install --no-cache-dir -r requirements.txt
_SETUP

CMD ["python", "-m", "src"]
