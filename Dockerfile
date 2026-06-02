# syntax=docker/dockerfile:1
# artifacts: false
# platforms: linux/amd64
FROM ghcr.io/astral-sh/uv:0.11-python3.14-trixie-slim

# CI args
ARG BRANCH
ARG BUILD_VERSION
ARG COMMIT
# note: BUILD_VERSION may be blank

ENV BRANCH=${BRANCH}
ENV BUILD_VERSION=${BUILD_VERSION}
ENV COMMIT=${COMMIT}
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

VOLUME /data
WORKDIR /app/

# Copy only necessary files for installation and runtime
COPY pyproject.toml uv.lock README.md ./
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
uv sync --frozen --no-dev --no-install-project --python python --no-python-downloads

# set ownership of app and data directories
mkdir -p /data
chown -R supportbot:supportbot /app /data "${VIRTUAL_ENV}"
_SETUP

# switch to non-root user
USER supportbot

CMD ["python", "-m", "src"]
