#!/usr/bin/env bash

set -euo pipefail

ISO15118_REPO_DIR="${ISO15118_REPO_DIR:-$HOME/src/iso15118}"

print_check() {
  local label="$1"
  local cmd="$2"

  if command -v "$cmd" >/dev/null 2>&1; then
    echo "[ok] $label: $(command -v "$cmd")"
  else
    echo "[missing] $label: $cmd"
  fi
}

echo "ISO 15118-2 WSL2 bootstrap check"
echo "Target repo dir: $ISO15118_REPO_DIR"
echo

print_check "git" git
print_check "make" make
print_check "openssl" openssl
print_check "python3" python3
print_check "poetry" poetry
print_check "java" java
print_check "ip" ip

echo
echo "Recommended clone command:"
echo "  git clone https://github.com/EcoG-io/iso15118 \"$ISO15118_REPO_DIR\""
echo
echo "Recommended Ubuntu packages:"
echo "  sudo apt update"
echo "  sudo apt install -y openjdk-17-jre python3-pip python3-venv make openssl"
echo "  curl -sSL https://install.python-poetry.org | python3 -"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Network check:"
echo "  ip -brief address"
echo
echo "Expected next steps after clone:"
echo "  cd \"$ISO15118_REPO_DIR/iso15118/shared/pki\""
echo "  ./create_certs.sh -v iso-2"
echo "  cd \"$ISO15118_REPO_DIR\""
echo "  cp .env.dev.local .env"
echo "  poetry install"
echo
echo "Run paths:"
echo "  bash tools/iso15118/run-local.sh secc"
echo "  bash tools/iso15118/run-local.sh evcc"
