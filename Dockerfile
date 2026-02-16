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

VOLUME /data
WORKDIR /app/

# Copy only necessary files for installation and runtime
COPY pyproject.toml .
COPY src/ src/
COPY assets/ assets/

RUN <<_SETUP
#!/bin/bash
set -e

# install system dependencies
apt-get update -y
apt-get install -y --no-install-recommends git
apt-get clean
rm -rf /var/lib/apt/lists/*

# create non-root user
useradd -m -u 1000 -s /bin/bash supportbot

# write the version to the version file
cat > src/common/version.py <<EOF
"""Version information for support-bot."""

__version__ = "${BUILD_VERSION}"
EOF

# install python dependencies
python -m pip install --no-cache-dir .

# set ownership of app and data directories
mkdir -p /data
chown -R supportbot:supportbot /app /data
_SETUP

# switch to non-root user
USER supportbot

CMD ["python", "-m", "src"]
