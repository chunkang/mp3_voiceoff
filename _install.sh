#!/usr/bin/env bash
# _install.sh - Install mp3_voiceoff into an isolated venv under ~/.local/share
#               and drop a thin launcher into ~/bin.
#
# Author : Chun Kang <ck@ckii.com>
# License: Apache License 2.0

set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="mp3_voiceoff.py"
SRC="${SRC_DIR}/${SCRIPT}"

APP_DIR="${HOME}/.local/share/mp3_voiceoff"
VENV_DIR="${APP_DIR}/venv"
SCRIPT_DEST="${APP_DIR}/${SCRIPT}"
BIN_DIR="${HOME}/bin"
BIN_DEST="${BIN_DIR}/mp3_voiceoff"

log() { printf '[install] %s\n' "$*"; }
die() { printf '[install] ERROR: %s\n' "$*" >&2; exit 1; }

[[ -f "$SRC" ]] || die "$SRC not found"

# ---------------------------------------------------------------------------
# System deps: python3 + ffmpeg
# ---------------------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3 is required"

install_ffmpeg() {
    local os sudo_cmd=""
    os="$(uname -s)"
    [[ $EUID -ne 0 && "$(command -v sudo || true)" ]] && sudo_cmd="sudo"

    case "$os" in
        Darwin)
            command -v brew >/dev/null 2>&1 || die "Homebrew is required on macOS. Install from https://brew.sh/"
            brew install ffmpeg
            ;;
        Linux)
            if   command -v apt-get >/dev/null 2>&1; then
                $sudo_cmd apt-get update
                $sudo_cmd apt-get install -y ffmpeg
            elif command -v dnf     >/dev/null 2>&1; then
                $sudo_cmd dnf install -y epel-release || true
                $sudo_cmd dnf install -y ffmpeg
            elif command -v yum     >/dev/null 2>&1; then
                $sudo_cmd yum install -y epel-release || true
                $sudo_cmd yum install -y ffmpeg
            elif command -v pacman  >/dev/null 2>&1; then
                $sudo_cmd pacman -S --noconfirm ffmpeg
            elif command -v zypper  >/dev/null 2>&1; then
                $sudo_cmd zypper install -y ffmpeg
            elif command -v apk     >/dev/null 2>&1; then
                $sudo_cmd apk add --no-cache ffmpeg
            else
                die "No supported package manager found. Install ffmpeg manually."
            fi
            ;;
        *)
            die "Unsupported OS: $os"
            ;;
    esac
}

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    log "ffmpeg not found; installing..."
    install_ffmpeg
fi

# ---------------------------------------------------------------------------
# venv + Python deps
# ---------------------------------------------------------------------------
mkdir -p "$APP_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating venv: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

log "Upgrading pip inside venv"
"$VENV_DIR/bin/pip" install --upgrade pip

log "Installing Python dependencies (spleeter, mutagen, pydub) into venv"
"$VENV_DIR/bin/pip" install spleeter mutagen pydub

# ---------------------------------------------------------------------------
# Copy script + launcher
# ---------------------------------------------------------------------------
cp "$SRC" "$SCRIPT_DEST"
chmod +x "$SCRIPT_DEST"
log "Copied $SCRIPT -> $SCRIPT_DEST"

mkdir -p "$BIN_DIR"

cat > "$BIN_DEST" <<EOF
#!/usr/bin/env bash
# mp3_voiceoff - launcher that runs mp3_voiceoff.py inside its dedicated venv
#
# Author : Chun Kang <ck@ckii.com>
# License: Apache License 2.0
exec "${VENV_DIR}/bin/python" "${SCRIPT_DEST}" "\$@"
EOF
chmod +x "$BIN_DEST"
log "Installed launcher: $BIN_DEST"

case ":$PATH:" in
    *":${BIN_DIR}:"*) ;;
    *) log "Note: ${BIN_DIR} is not in your PATH. Add it to your shell rc file." ;;
esac

log "Done."
