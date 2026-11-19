#!/usr/bin/env bash
# WSL/Ubuntu first-time setup. Run from the repository root.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2
  exit 1
fi

# GDAL's Python bindings (from PyPI via uv) compile/link against Ubuntu libgdal.
sudo apt-get update
sudo apt-get install -y libgdal-dev gdal-bin build-essential

GDAL_VERSION="$(gdal-config --version)"
echo "Native GDAL version: ${GDAL_VERSION}"
uv python install 3.12

# Record GDAL as a normal uv dependency in pyproject.toml and uv.lock.
# We do not put one universal version in the template since Ubuntu releases
# ship different native libgdal versions.
uv add "GDAL[numpy]==${GDAL_VERSION}"
uv sync

if [ ! -e config/local.toml ]; then
  cp config/local.example.toml config/local.toml
fi

uv run python scripts/check_environment.py
printf '\nOpen this directory in VS Code (WSL) and select .venv/bin/python as the notebook kernel.\n'
printf 'Use: code .\n'
