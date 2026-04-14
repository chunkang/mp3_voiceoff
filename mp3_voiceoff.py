#!/usr/bin/env python3
# mp3_voiceoff.py - Remove vocals from MP3 files using Spleeter (AI source separation)
#
# Author : Chun Kang <ck@ckii.com>
# License: Apache License 2.0
#
# Usage:
#   ./mp3_voiceoff.py                      # process every *.mp3 under CWD (recursive)
#   ./mp3_voiceoff.py "*.mp3"              # same, explicit pattern
#   ./mp3_voiceoff.py "hel*.mp3"           # recursive basename glob
#   ./mp3_voiceoff.py "son?.mp3"           # '?' matches a single character
#   ./mp3_voiceoff.py song.mp3 intro.mp3   # explicit file list
#
# Glob metacharacters: '*', '?', '[...]'. Quote patterns so your shell does
# not pre-expand them before the script recurses.
#
# Output files are written next to each source as <name>_MR.mp3. Original ID3
# tags are preserved, and the title tag is suffixed with " (MR)". If the
# source has no title tag, the filename (without extension) is used.

from __future__ import annotations

import argparse
import fnmatch
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TAG = "[mp3_voiceoff]"
REQUIRED_PKGS = ["spleeter", "mutagen", "pydub"]

CREDIT = (
    "mp3_voiceoff - Remove vocals from MP3 files using Spleeter\n"
    "Author : Chun Kang <ck@ckii.com>\n"
    "License: Apache License 2.0"
)

APP_DIR = Path.home() / ".local" / "share" / "mp3_voiceoff"
VENV_DIR = APP_DIR / "venv"
BOOTSTRAP_ENV_FLAG = "MP3_VOICEOFF_BOOTSTRAPPED"

# Spleeter's pinned TensorFlow/numpy only build on CPython 3.8-3.10.
SUPPORTED_PY = ((3, 8), (3, 9), (3, 10))
PREFERRED_PY = (3, 10)


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"{TAG} {msg}")


def warn(msg: str) -> None:
    print(f"{TAG} WARN: {msg}", file=sys.stderr)


def die(msg: str, code: int = 1) -> "None":
    print(f"{TAG} ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Self-bootstrap: ensure ffmpeg + dedicated venv + Python deps, then re-exec
# ---------------------------------------------------------------------------
def _venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _running_in_managed_venv() -> bool:
    vp = _venv_python()
    if not vp.exists():
        return False
    try:
        return Path(sys.executable).resolve() == vp.resolve()
    except OSError:
        return False


def _python_version(exe: str | Path) -> tuple[int, int] | None:
    try:
        out = subprocess.check_output(
            [str(exe), "-c", "import sys;print(sys.version_info.major,sys.version_info.minor)"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip().split()
        return (int(out[0]), int(out[1]))
    except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
        return None


def _is_supported_py(ver: tuple[int, int] | None) -> bool:
    return ver is not None and ver in SUPPORTED_PY


def _find_compatible_python() -> Path | None:
    candidates: list[str] = []
    # Preferred first, then the rest.
    order = [PREFERRED_PY] + [v for v in SUPPORTED_PY if v != PREFERRED_PY]
    for major, minor in order:
        candidates.append(f"python{major}.{minor}")
    # Homebrew keg-only locations on macOS.
    if platform.system() == "Darwin":
        for major, minor in order:
            for prefix in ("/opt/homebrew/opt", "/usr/local/opt"):
                candidates.append(f"{prefix}/python@{major}.{minor}/bin/python{major}.{minor}")

    for c in candidates:
        path = shutil.which(c) if "/" not in c else (c if Path(c).exists() else None)
        if not path:
            continue
        if _is_supported_py(_python_version(path)):
            return Path(path)
    return None


def _install_compatible_python() -> Path | None:
    system = platform.system()
    target = f"python@{PREFERRED_PY[0]}.{PREFERRED_PY[1]}"
    if system == "Darwin":
        if not shutil.which("brew"):
            die("Homebrew is required on macOS. Install from https://brew.sh/")
        log(f"Installing {target} via Homebrew (Spleeter needs Python <=3.10)")
        subprocess.check_call(["brew", "install", target])
    elif system == "Linux":
        sudo = [] if os.geteuid() == 0 else (["sudo"] if shutil.which("sudo") else [])
        pkg = f"python{PREFERRED_PY[0]}.{PREFERRED_PY[1]}"
        if shutil.which("apt-get"):
            log(f"Installing {pkg} via apt (Spleeter needs Python <=3.10)")
            subprocess.check_call(sudo + ["apt-get", "update"])
            subprocess.check_call(sudo + ["apt-get", "install", "-y", pkg, f"{pkg}-venv"])
        else:
            return None
    else:
        return None
    return _find_compatible_python()


def _venv_is_compatible() -> bool:
    vp = _venv_python()
    if not vp.exists():
        return False
    return _is_supported_py(_python_version(vp))


def _missing_python_packages() -> list[str]:
    import importlib.util

    return [p for p in REQUIRED_PKGS if importlib.util.find_spec(p) is None]


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return

    system = platform.system()
    log("ffmpeg not found. Attempting to install...")

    if system == "Darwin":
        if not shutil.which("brew"):
            die("Homebrew is required on macOS. Install from https://brew.sh/")
        subprocess.check_call(["brew", "install", "ffmpeg"])
    elif system == "Linux":
        sudo = [] if os.geteuid() == 0 else (["sudo"] if shutil.which("sudo") else [])
        if not sudo and os.geteuid() != 0:
            die("sudo is required to install packages.")

        if shutil.which("apt-get"):
            subprocess.check_call(sudo + ["apt-get", "update"])
            subprocess.check_call(sudo + ["apt-get", "install", "-y", "ffmpeg"])
        elif shutil.which("dnf"):
            subprocess.call(sudo + ["dnf", "install", "-y", "epel-release"])
            subprocess.check_call(sudo + ["dnf", "install", "-y", "ffmpeg"])
        elif shutil.which("yum"):
            subprocess.call(sudo + ["yum", "install", "-y", "epel-release"])
            subprocess.check_call(sudo + ["yum", "install", "-y", "ffmpeg"])
        elif shutil.which("pacman"):
            subprocess.check_call(sudo + ["pacman", "-S", "--noconfirm", "ffmpeg"])
        elif shutil.which("zypper"):
            subprocess.check_call(sudo + ["zypper", "install", "-y", "ffmpeg"])
        elif shutil.which("apk"):
            subprocess.check_call(sudo + ["apk", "add", "--no-cache", "ffmpeg"])
        else:
            die("No supported package manager found. Install ffmpeg manually.")
    else:
        die(f"Unsupported OS: {system}")

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        die("ffmpeg still not available after install.")


def _create_venv() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)

    py = _find_compatible_python()
    if py is None:
        py = _install_compatible_python()
    if py is None:
        die(
            "Could not find or install a compatible Python interpreter. "
            f"Spleeter requires CPython {SUPPORTED_PY[0][0]}.{SUPPORTED_PY[0][1]}-"
            f"{SUPPORTED_PY[-1][0]}.{SUPPORTED_PY[-1][1]}."
        )

    log(f"Creating venv with {py}: {VENV_DIR}")
    try:
        subprocess.check_call([str(py), "-m", "venv", str(VENV_DIR)])
    except subprocess.CalledProcessError:
        # Debian/Ubuntu may ship Python without the venv module.
        if platform.system() == "Linux" and shutil.which("apt-get"):
            log("python3-venv appears to be missing; installing it...")
            sudo = [] if os.geteuid() == 0 else (["sudo"] if shutil.which("sudo") else [])
            subprocess.check_call(sudo + ["apt-get", "install", "-y", "python3-venv"])
            subprocess.check_call([str(py), "-m", "venv", str(VENV_DIR)])
        else:
            raise


def _pip_install_deps() -> None:
    pip = _venv_python().with_name("pip")
    log("Upgrading pip inside venv")
    subprocess.check_call([str(pip), "install", "--upgrade", "pip"])
    log(f"Installing {', '.join(REQUIRED_PKGS)} into venv")
    subprocess.check_call([str(pip), "install", *REQUIRED_PKGS])


def bootstrap_and_reexec() -> None:
    ensure_ffmpeg()

    if VENV_DIR.exists() and not _venv_is_compatible():
        log(f"Existing venv uses an unsupported Python; recreating: {VENV_DIR}")
        shutil.rmtree(VENV_DIR)

    if not VENV_DIR.exists():
        _create_venv()

    # Re-exec inside the venv so pip/imports happen with its interpreter.
    if not _running_in_managed_venv():
        if os.environ.get(BOOTSTRAP_ENV_FLAG) == "1":
            die("bootstrap loop detected; venv is not usable")
        vp = _venv_python()
        env = os.environ.copy()
        env[BOOTSTRAP_ENV_FLAG] = "1"
        os.execve(str(vp), [str(vp), str(Path(__file__).resolve()), *sys.argv[1:]], env)

    if _missing_python_packages():
        _pip_install_deps()
        still = _missing_python_packages()
        if still:
            die(f"Still missing after install: {', '.join(still)}")


def spleeter_command() -> list[str]:
    if shutil.which("spleeter"):
        return ["spleeter"]
    return [sys.executable, "-m", "spleeter"]


# ---------------------------------------------------------------------------
# File discovery (recursive basename glob)
# ---------------------------------------------------------------------------
def find_files(patterns: list[str]) -> list[Path]:
    root = Path(".")
    if not patterns:
        patterns = ["*.mp3"]

    results: list[Path] = []
    for pat in patterns:
        p = Path(pat)
        if p.is_file():
            results.append(p)
            continue

        base_pat = Path(pat).name.lower()
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            name_lower = f.name.lower()
            if name_lower.endswith("_mr.mp3"):
                continue
            if fnmatch.fnmatch(name_lower, base_pat):
                results.append(f)

    seen: set[Path] = set()
    unique: list[Path] = []
    for f in results:
        key = f.resolve()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


# ---------------------------------------------------------------------------
# ID3 tag handling
# ---------------------------------------------------------------------------
def read_title(path: Path) -> str:
    try:
        from mutagen.easyid3 import EasyID3
        tags = EasyID3(str(path))
        title = tags.get("title", [None])[0]
        if title:
            return title
    except Exception:
        pass
    return path.stem


def apply_tags(src: Path, dst: Path, new_title: str) -> None:
    from mutagen.id3 import ID3, ID3NoHeaderError, TIT2
    from mutagen.mp3 import MP3

    try:
        src_id3 = ID3(str(src))
    except ID3NoHeaderError:
        src_id3 = None
    except Exception as e:
        warn(f"could not read source tags: {e}")
        src_id3 = None

    try:
        dst_id3 = ID3(str(dst))
    except ID3NoHeaderError:
        mp3 = MP3(str(dst))
        mp3.add_tags()
        mp3.save()
        dst_id3 = ID3(str(dst))

    if src_id3 is not None:
        dst_id3.clear()
        for frame in src_id3.values():
            dst_id3.add(frame)

    dst_id3.delall("TIT2")
    dst_id3.add(TIT2(encoding=3, text=new_title))
    dst_id3.save(str(dst), v2_version=3)


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------
def process_file(src: Path) -> bool:
    if src.name.lower().endswith("_mr.mp3"):
        log(f"Skip (already MR): {src}")
        return True

    out_path = src.with_name(f"{src.stem}_MR.mp3")
    if out_path.exists():
        log(f"Skip (exists): {out_path}")
        return True

    log(f"Processing: {src}")
    new_title = f"{read_title(src)} (MR)"

    with tempfile.TemporaryDirectory(prefix="mp3_voiceoff_") as tmp:
        tmp_dir = Path(tmp)

        sep = subprocess.run(
            spleeter_command() + [
                "separate",
                "-p", "spleeter:2stems",
                "-o", str(tmp_dir),
                "-c", "mp3",
                "-b", "192k",
                str(src),
            ],
            capture_output=True, text=True,
        )
        if sep.returncode != 0:
            warn(f"spleeter failed for {src}")
            if sep.stderr.strip():
                for line in sep.stderr.strip().splitlines():
                    print(f"  {line}", file=sys.stderr)
            return False

        # Spleeter writes to <tmp_dir>/<stem>/accompaniment.mp3
        accompaniment = tmp_dir / src.stem / "accompaniment.mp3"
        if not accompaniment.exists():
            # Some spleeter versions fall back to .wav regardless of -c
            wav = tmp_dir / src.stem / "accompaniment.wav"
            if wav.exists():
                enc = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                     "-i", str(wav),
                     "-codec:a", "libmp3lame", "-q:a", "2",
                     str(out_path)],
                    capture_output=True, text=True,
                )
                if enc.returncode != 0:
                    warn(f"ffmpeg encode failed: {src}")
                    for line in enc.stderr.strip().splitlines():
                        print(f"  {line}", file=sys.stderr)
                    if out_path.exists():
                        out_path.unlink()
                    return False
            else:
                warn(f"spleeter produced no accompaniment track for {src}")
                return False
        else:
            shutil.move(str(accompaniment), str(out_path))

    try:
        apply_tags(src, out_path, new_title)
    except Exception as e:
        warn(f"tag copy issue for {out_path}: {e}")

    log(f"  -> {out_path}")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def print_credit() -> None:
    if os.environ.get(BOOTSTRAP_ENV_FLAG) == "1":
        # Suppress duplicate banner on the post-bootstrap re-exec.
        return
    bar = "=" * 60
    print(bar)
    print(CREDIT)
    print(bar)


def main() -> None:
    print_credit()
    parser = argparse.ArgumentParser(
        description="Remove vocals from MP3 files using Spleeter.",
    )
    parser.add_argument(
        "patterns",
        nargs="*",
        help="Files or glob patterns (e.g. '*.mp3', 'hel*.mp3', 'song?.mp3'). "
             "Default: every *.mp3 under the current directory, recursively.",
    )
    args = parser.parse_args()

    if not _running_in_managed_venv() or _missing_python_packages():
        bootstrap_and_reexec()

    ensure_ffmpeg()

    files = find_files(args.patterns)
    if not files:
        log("No MP3 files matched.")
        return

    log(f"Found {len(files)} file(s) to process.")
    ok = fail = 0
    for f in files:
        try:
            if process_file(f):
                ok += 1
            else:
                fail += 1
        except KeyboardInterrupt:
            warn("interrupted by user")
            break
        except Exception as e:
            warn(f"unhandled error on {f}: {e}")
            fail += 1

    log(f"Done. success={ok} failed={fail}")


if __name__ == "__main__":
    main()
