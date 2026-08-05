#!/bin/sh
# Max the Golden Token Retrieval — installer.
#   curl -fsSL https://raw.githubusercontent.com/PhilbertChristian/max/main/install.sh | sh
# Installs pipx if needed, installs Max, and hands you to `max init`,
# where Max introduces himself and checks his own setup.
set -e

if ! command -v pipx >/dev/null 2>&1; then
  echo "  (installing pipx first)"
  if command -v brew >/dev/null 2>&1; then
    brew install pipx >/dev/null
  else
    python3 -m pip install --user pipx
  fi
  pipx ensurepath >/dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:$PATH"
fi

pipx install --force git+https://github.com/PhilbertChristian/max
export PATH="$HOME/.local/bin:$PATH"
exec max init
