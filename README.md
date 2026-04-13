# mp3_voiceoff

**Author:** Chun Kang <ck@ckii.com>
**License:** Apache License 2.0

Remove the vocal track from MP3 audio files using [Spleeter](https://github.com/deezer/spleeter)
(Deezer's deep-learning source-separation model) and write a new
`<name>_MR.mp3` alongside each source, preserving the original ID3 tags.

## How it works

`mp3_voiceoff.py` invokes Spleeter's `2stems` model to split each source into
`vocals` and `accompaniment`. The accompaniment track is written out as
`<name>_MR.mp3`. This produces dramatically cleaner karaoke tracks than the
classic L/R-subtraction trick, because Spleeter is a neural network trained on
real mixed/unmixed stem pairs.

For every processed file:

- A new file is written next to the source as `<name>_MR.mp3`.
- All ID3 tags from the source are copied onto the output via `mutagen`.
- The `title` tag gets ` (MR)` appended. If the source has no title tag, the
  filename (without extension) is used as the base.

## Requirements

- Python 3.8+ (Spleeter currently requires Python <3.11 for TensorFlow)
- `ffmpeg` and `ffprobe` (auto-installed on first run if missing)
- Python packages: `spleeter`, `mutagen`, `pydub` (auto-installed on first run)

`mp3_voiceoff.py` is self-bootstrapping. The **first time** you run it, it
will — without any external help — do everything needed so Spleeter's heavy
dependency tree (TensorFlow, numpy, etc.) never collides with your system
Python:

1. Installs `ffmpeg` via the native package manager if it is not already
   available.
2. Creates a dedicated venv at `~/.local/share/mp3_voiceoff/venv`.
3. `pip install`s `spleeter`, `mutagen`, and `pydub` into that venv.
4. Re-executes itself using the venv's Python and runs normally.
5. Spleeter downloads its pretrained 2stems model (~75 MB, one-time) into
   `./pretrained_models/` on the first separation call.

Subsequent runs reuse the same venv and skip the bootstrap path.

| Platform                      | Package manager |
|-------------------------------|-----------------|
| macOS                         | Homebrew (`brew`) |
| Debian / Ubuntu               | `apt-get`       |
| Fedora / RHEL 8+ / CentOS 8+  | `dnf`           |
| CentOS 7 / RHEL 7             | `yum` + EPEL    |
| Arch                          | `pacman`        |
| openSUSE                      | `zypper`        |
| Alpine                        | `apk`           |

On macOS, [Homebrew](https://brew.sh/) must be installed first.

## Installation

```sh
git clone <this-repo>
cd mp3_voiceoff

# Option A: run in place — first run bootstraps everything
./mp3_voiceoff.py

# Option B: put it on PATH as `mp3_voiceoff` (no .py extension)
./_install.sh
```

`_install.sh` is just a thin helper that copies `mp3_voiceoff.py` to
`~/bin/mp3_voiceoff` (creating `~/bin` if needed). All dependency
installation — ffmpeg, the dedicated venv, and the Python packages — is
handled by `mp3_voiceoff` itself on its first run.

## Usage

```sh
# Process every *.mp3 under the current directory (recursively)
mp3_voiceoff

# Process every *.mp3 (explicit, same as above)
mp3_voiceoff "*.mp3"

# Recursive glob by basename — quote the pattern so the shell does not expand it
mp3_voiceoff "hel*.mp3"

# '?' matches a single character; '[...]' character classes also work
mp3_voiceoff "son?.mp3"
mp3_voiceoff "track_[0-9].mp3"

# Explicit file list
mp3_voiceoff song.mp3 path/to/intro.mp3
```

### Notes

- When a glob pattern is given, the script searches **recursively** through
  subdirectories matching the basename pattern (case-insensitive).
- Glob metacharacters supported: `*`, `?`, `[...]`.
- Quote glob patterns so your shell does not pre-expand them before the
  script can recurse.
- Files already ending in `_MR.mp3` are skipped, and existing outputs are not
  overwritten.
- Spleeter is compute-heavy. Expect a few seconds to a minute per track on a
  typical laptop, plus a one-time model download on first run.

## Example

```sh
$ mp3_voiceoff "love*.mp3"
[mp3_voiceoff] Found 2 file(s) to process.
[mp3_voiceoff] Processing: ./albums/love_song.mp3
[mp3_voiceoff]   -> ./albums/love_song_MR.mp3
[mp3_voiceoff] Processing: ./b-sides/lovely.mp3
[mp3_voiceoff]   -> ./b-sides/lovely_MR.mp3
[mp3_voiceoff] Done. success=2 failed=0
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the
full text.

Copyright 2026 Chun Kang <ck@ckii.com>
