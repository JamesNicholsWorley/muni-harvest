#!/usr/bin/env bash
# Idempotent VM setup / re-provision (Ubuntu 24.04). Same work as cloud-init.yaml,
# but re-runnable to update an existing box. Run as root: bash setup_vm.sh
set -euo pipefail

REPO=/opt/muni-harvest
BRANCH=${1:-main}

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git wget unzip tmux \
  fonts-liberation ca-certificates

if ! command -v google-chrome >/dev/null 2>&1; then
  wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb
  apt-get install -y /tmp/chrome.deb
  rm -f /tmp/chrome.deb
fi

if [ -d "$REPO/.git" ]; then
  git -C "$REPO" fetch --quiet origin "$BRANCH"
  git -C "$REPO" reset --hard "origin/$BRANCH"
else
  git clone https://github.com/JamesNicholsWorley/muni-harvest.git "$REPO"
fi

[ -d "$REPO/.venv" ] || python3 -m venv "$REPO/.venv"
"$REPO/.venv/bin/pip" install --upgrade pip
"$REPO/.venv/bin/pip" install -e "$REPO[live,s3]"
[ -f "$REPO/.env" ] || touch "$REPO/.env"

echo "[OK] setup complete. Put secrets in $REPO/.env, then:"
echo "  cd $REPO && .venv/bin/muni-harvest store ping"
echo "  tmux new -s discover '.venv/bin/muni-harvest discover'"
