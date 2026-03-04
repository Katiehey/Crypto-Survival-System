#!/usr/bin/env bash
set -euo pipefail
# Simple provisioning helper for an Ubuntu-like VPS.
# Usage: sudo ./scripts/provision_vps.sh /opt/crypto-survival-system

DEST=${1:-/opt/crypto-survival-system}
REPO=https://github.com/Katiehey/Crypto-Survival-System.git

echo "Provisioning VPS into $DEST"

if [ ! -d "$DEST" ]; then
  mkdir -p "$DEST"
  git clone "$REPO" "$DEST"
else
  echo "Directory exists; pulling latest"
  git -C "$DEST" pull --ff-only || true
fi

cd "$DEST"

if [ ! -f .env ]; then
  if [ -f .env.template ]; then
    cp .env.template .env
    echo "Created .env from .env.template — edit it with secrets before starting services."
  else
    echo "No .env.template found; create .env with required secrets." > /dev/null
  fi
fi

echo "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm -f get-docker.sh

echo "Ensuring docker-compose is available (plugin)..."
if ! command -v docker-compose >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose (plugin) available"
  else
    echo "docker compose not found — you may need to install docker-compose plugin or use 'docker compose'"
  fi
fi

echo "Building and starting canary via docker compose"
cd deploy
docker compose build --pull --no-cache || true
docker compose up -d

echo "Provisioning complete. Review .env and journalctl -u canary.service if using systemd unit."
