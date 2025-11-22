# syntax=docker/dockerfile:1
# artifacts: false
# platforms: linux/amd64
FROM python:3.14-slim-bookworm

# CI args
ARG BRANCH
ARG BUILD_VERSION
ARG COMMIT
# note: BUILD_VERSION may be blank

ENV BRANCH=${BRANCH}
ENV BUILD_VERSION=${BUILD_VERSION}
ENV COMMIT=${COMMIT}

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
sed -i "s/version = '0.0.0'/version = '${BUILD_VERSION}'/g" src/common/common.py

# install dependencies
python -m pip install --no-cache-dir -r requirements.txt
_SETUP

CMD ["python", "-m", "src"]
