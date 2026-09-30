"""Engine AI DeepFilterNet melalui binary `deep-filter` resmi.

Binary diambil dari rilis GitHub DeepFilterNet (lisensi MIT/Apache-2.0), diunduh
sekali ke folder cache pengguna, dan diverifikasi dengan SHA-256 sebelum dipakai.
"""

from __future__ import annotations

import hashlib
import math
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path

VERSION = "0.5.6"
_RELEASE_URL = (
    f"https://github.com/Rikorose/DeepFilterNet/releases/download/v{VERSION}/{{name}}"
)
# (sys.platform, mesin) -> (nama aset rilis, SHA-256)
_ASSETS = {
    ("win32", "x86_64"): (
        f"deep-filter-{VERSION}-x86_64-pc-windows-msvc.exe",
        "75e11fa16445f560cb6b021521ddb89e89270d13b83089705d98776f58fd7915",
    ),
    ("linux", "x86_64"): (
        f"deep-filter-{VERSION}-x86_64-unknown-linux-musl",
        "70775e251eee44c0f2451a1e833326cf8bcbbe304d3e7cd12851e6fce72ef7da",
    ),
    ("darwin", "arm64"): (
        f"deep-filter-{VERSION}-aarch64-apple-darwin",
        "4601e7f4e4c03e59a4c5b5000216ef3add3e808799cfccd95e14e83ea4611081",
    ),
    ("darwin", "x86_64"): (
        f"deep-filter-{VERSION}-x86_64-apple-darwin",
        "d3be84003acb7c23e738ad7f70a158ec779a8d233a82e7fa3e717d112eb5b50f",
    ),
}

# Argumen tambahan per preset. Default binary = redaman penuh.
PRESET_ARGS = {
    "light": ["--atten-lim-db", "20"],
    "balanced": [],
    "strong": ["--pf"],
}

# Perkiraan waktu proses per detik audio (per track stereo), untuk estimasi progres.
_SECONDS_PER_AUDIO_SECOND = 0.12

_SUBPROCESS_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class DeepFilterError(RuntimeError):
    """Kesalahan saat menyiapkan atau menjalankan DeepFilterNet."""


def _asset() -> tuple[str, str]:
    # Di Windows platform.machine() berasal dari environment variable dan bisa
    # kosong; anggap x86_64 untuk Python 64-bit.
    machine = platform.machine().lower() or ("x86_64" if sys.maxsize > 2**32 else "x86")
    machine = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    try:
        return _ASSETS[(sys.platform, machine)]
    except KeyError as exc:
        raise DeepFilterError(
            f"Engine deepfilter belum tersedia untuk {sys.platform}/{platform.machine()}. "
            "Gunakan engine spectral atau rnnoise, atau set DENOISE_DEEPFILTER ke "
            "lokasi binary deep-filter."
        ) from exc


def binary_name() -> str:
    return _asset()[0]


def cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "local-denoise"


def _bundled_path() -> Path | None:
    # Executable PyInstaller menyertakan binary di folder "deepfilter".
    bundle = getattr(sys, "_MEIPASS", None)
    if not bundle:
        return None
    candidate = Path(bundle) / "deepfilter" / binary_name()
    return candidate if candidate.is_file() else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    destination: Path,
    on_progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    name, expected = _asset()
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    try:
        with urllib.request.urlopen(_RELEASE_URL.format(name=name), timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            with partial.open("wb") as handle:
                while chunk := response.read(256 * 1024):
                    if cancel is not None and cancel.is_set():
                        raise DeepFilterError("Proses dibatalkan.")
                    handle.write(chunk)
                    received += len(chunk)
                    if on_progress and total:
                        on_progress(received / total)
        if _sha256(partial) != expected:
            raise DeepFilterError(
                "File engine deepfilter yang diunduh tidak cocok dengan checksum. "
                "Coba lagi atau periksa koneksi internet."
            )
        if sys.platform != "win32":
            partial.chmod(0o755)
        partial.replace(destination)
    except OSError as exc:
        raise DeepFilterError(
            f"Gagal mengunduh engine deepfilter: {exc}. Pastikan terhubung ke "
            "internet untuk pemakaian pertama."
        ) from exc
    finally:
        partial.unlink(missing_ok=True)
    return destination


def resolve_binary(
    allow_download: bool = True,
    on_status: Callable[[str], None] | None = None,
    on_progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
) -> Path | None:
    """Cari binary deep-filter; unduh ke cache bila belum ada.

    Mengembalikan None hanya jika binary belum ada dan `allow_download` False.
    """
    configured = os.environ.get("DENOISE_DEEPFILTER")
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_file():
            raise DeepFilterError(f"Binary deep-filter tidak ditemukan di: {candidate}")
        return candidate.resolve()

    bundled = _bundled_path()
    if bundled:
        return bundled

    cached = cache_dir() / binary_name()
    if cached.is_file():
        return cached
    if not allow_download:
        return None
    if on_status:
        on_status("Mengunduh engine AI DeepFilterNet (sekali saja)...")
    return download(cached, on_progress, cancel)


def build_command(
    binary: Path | str, inputs: Sequence[Path], output_dir: Path, preset_name: str
) -> list[str]:
    try:
        preset_args = PRESET_ARGS[preset_name]
    except KeyError as exc:
        choices = ", ".join(PRESET_ARGS)
        raise DeepFilterError(
            f"Preset '{preset_name}' tidak dikenal. Pilihan yang tersedia: {choices}."
        ) from exc
    return [
        str(binary),
        "--compensate-delay",
        *preset_args,
        "--output-dir",
        str(output_dir),
        *(str(path) for path in inputs),
    ]


def run(
    command: list[str],
    audio_seconds: float,
    on_progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
) -> None:
    """Jalankan deep-filter. Binary tidak melaporkan progres, jadi progres
    diperkirakan dari waktu berjalan dan tidak pernah mencapai 100% sebelum selesai."""
    expected = max(audio_seconds * _SECONDS_PER_AUDIO_SECOND, 1.0)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_SUBPROCESS_FLAGS,
    )
    stderr_chunks: list[str] = []
    reader = threading.Thread(
        target=lambda: stderr_chunks.append(process.stderr.read()), daemon=True
    )
    reader.start()
    started = time.monotonic()
    try:
        while True:
            try:
                returncode = process.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                pass
            if cancel is not None and cancel.is_set():
                raise DeepFilterError("Proses dibatalkan.")
            if on_progress:
                elapsed = time.monotonic() - started
                on_progress(0.95 * (1 - math.exp(-elapsed / expected)))
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        reader.join(timeout=5)

    if returncode != 0:
        lines = [line.strip() for line in "".join(stderr_chunks).splitlines() if line.strip()]
        detail = "\n".join(lines[-6:]) or f"kode {returncode}"
        raise DeepFilterError(f"DeepFilterNet gagal memproses audio:\n{detail}")
    if on_progress:
        on_progress(1.0)
