#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <secc|evcc|test> [evcc_config_path]" >&2
  exit 1
fi

ROLE="$1"
EVCC_CONFIG_PATH_ARG="${2:-}"
ISO15118_REPO_DIR="${ISO15118_REPO_DIR:-$HOME/src/iso15118}"
DEFAULT_EVCC_CONFIG_PATH="${DEFAULT_EVCC_CONFIG_PATH:-iso15118/shared/examples/evcc/iso15118_2/evcc_config_eim_ac_auto_restart.json}"

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
    EVCC_CONFIG_PATH="${EVCC_CONFIG_PATH_ARG:-$DEFAULT_EVCC_CONFIG_PATH}"
    if [[ ! -f "$EVCC_CONFIG_PATH" ]]; then
      echo "Missing EVCC config: $EVCC_CONFIG_PATH" >&2
      exit 1
    fi
    poetry run python iso15118/evcc/main.py "$EVCC_CONFIG_PATH"
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

