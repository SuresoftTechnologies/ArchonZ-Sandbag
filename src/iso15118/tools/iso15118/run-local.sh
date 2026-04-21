#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <secc|evcc|test> [evcc_config_path]" >&2
  exit 1
fi

ROLE="$1"
EVCC_CONFIG_PATH_ARG="${2:-}"
ISO15118_REPO_DIR="${ISO15118_REPO_DIR:-$HOME/src/iso15118}"

if [[ ! -d "$ISO15118_REPO_DIR" ]]; then
  echo "Missing iso15118 repository: $ISO15118_REPO_DIR" >&2
  echo "Set ISO15118_REPO_DIR or clone the repository first." >&2
  exit 1
fi

cd "$ISO15118_REPO_DIR"

if [[ ! -f ".env" ]]; then
  echo "Missing .env in $ISO15118_REPO_DIR" >&2
  echo "Create it first: cp .env.dev.local .env" >&2
  exit 1
fi

case "$ROLE" in
  secc)
    poetry install
    poetry run python iso15118/secc/main.py
    ;;
  evcc)
    poetry install
    if [[ -n "$EVCC_CONFIG_PATH_ARG" ]]; then
      poetry run python iso15118/evcc/main.py "$EVCC_CONFIG_PATH_ARG"
    else
      poetry run python iso15118/evcc/main.py
    fi
    ;;
  test)
    poetry install
    poetry run pytest -vv tests/iso15118_2
    ;;
  *)
    echo "Unsupported role: $ROLE" >&2
    echo "Usage: $0 <secc|evcc|test> [evcc_config_path]" >&2
    exit 1
    ;;
esac

