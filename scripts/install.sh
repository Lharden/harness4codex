#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOURCE=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python "$SCRIPT_DIR/install.py" --source "$SOURCE" --codex-home "$CODEX_HOME" "$@"
