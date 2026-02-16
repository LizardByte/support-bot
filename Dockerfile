# syntax=docker/dockerfile:1
# artifacts: false
# platforms: linux/amd64
FROM python:3.13-slim-bookworm

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

# write the version to the version file
cat > src/common/version.py <<EOF
"""Version information for support-bot."""

__version__ = "${BUILD_VERSION}"
EOF

# install dependencies
python -m pip install --no-cache-dir .
_SETUP

CMD ["python", "-m", "src"]
