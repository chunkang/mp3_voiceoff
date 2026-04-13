#!/usr/bin/env bash
# _install.sh - Copy mp3_voiceoff.py into ~/bin as `mp3_voiceoff`.
#               The script self-bootstraps its venv + deps on first run,
#               so there is nothing else to install here.
#
# Author : Chun Kang <ck@ckii.com>
# License: Apache License 2.0

set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="mp3_voiceoff.py"
SRC="${SRC_DIR}/${SCRIPT}"
DEST_DIR="${HOME}/bin"
DEST="${DEST_DIR}/${SCRIPT%.py}"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: $SRC not found" >&2
    exit 1
fi

if [[ ! -d "$DEST_DIR" ]]; then
    echo "Creating $DEST_DIR"
    mkdir -p "$DEST_DIR"
fi

cp "$SRC" "$DEST"
chmod +x "$DEST"
echo "Installed: $DEST"
echo "First run will create a venv at ~/.local/share/mp3_voiceoff/venv and install dependencies."

case ":$PATH:" in
    *":${DEST_DIR}:"*) ;;
    *) echo "Note: ${DEST_DIR} is not in your PATH. Add it to your shell rc file." ;;
esac
