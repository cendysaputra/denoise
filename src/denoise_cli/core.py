from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}

VIDEO_EXTENSIONS = {
    ".avi",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ts",
    ".webm",
}


@dataclass(frozen=True)
class Preset:
    reduction: float
    noise_floor: float
    smoothing: int


PRESETS = {
    "light": Preset(reduction=8, noise_floor=-55, smoothing=4),
    "balanced": Preset(reduction=14, noise_floor=-50, smoothing=8),
    "strong": Preset(reduction=24, noise_floor=-45, smoothing=12),
}


class DenoiseError(RuntimeError):
    """A user-facing processing error."""


def media_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    supported = ", ".join(sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS))
    raise DenoiseError(
        f"Format '{suffix or '(tanpa ekstensi)'}' belum didukung. "
        f"Format yang didukung: {supported}"
    )


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.denoised{input_path.suffix}")


def resolve_ffmpeg(explicit_path: str | None = None) -> str:
    configured = explicit_path or os.environ.get("DENOISE_FFMPEG")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        discovered = shutil.which(configured)
        if discovered:
            return discovered
        raise DenoiseError(f"FFmpeg tidak ditemukan di: {configured}")

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        discovered = shutil.which("ffmpeg")
        if discovered:
            return discovered
        raise DenoiseError(
            "FFmpeg tidak tersedia. Jalankan 'python -m pip install -e .' "
            "dari folder proyek."
        ) from exc


def denoise_filter(
    preset_name: str,
    reduction: float | None = None,
    noise_floor: float | None = None,
) -> str:
    preset = PRESETS[preset_name]
    actual_reduction = preset.reduction if reduction is None else reduction
    actual_floor = preset.noise_floor if noise_floor is None else noise_floor

    if not 0.01 <= actual_reduction <= 97:
        raise DenoiseError("Nilai --reduction harus berada antara 0.01 dan 97.")
    if not -80 <= actual_floor <= -20:
        raise DenoiseError("Nilai --noise-floor harus berada antara -80 dan -20 dB.")

    return (
        f"afftdn=nr={actual_reduction:g}:nf={actual_floor:g}:"
        f"tn=1:gs={preset.smoothing}"
    )


def _audio_codec_args(output_path: Path, media_type: str) -> list[str]:
    suffix = output_path.suffix.lower()
    if suffix == ".wav":
        return ["-c:a", "pcm_s16le"]
    if suffix == ".flac":
        return ["-c:a", "flac"]
    if suffix == ".mp3":
        return ["-c:a", "libmp3lame", "-b:a", "192k"]
    if suffix in {".ogg", ".oga"}:
        return ["-c:a", "libvorbis", "-q:a", "5"]
    if suffix == ".opus" or (media_type == "video" and suffix == ".webm"):
        return ["-c:a", "libopus", "-b:a", "160k"]
    if suffix == ".wma":
        return ["-c:a", "wmav2", "-b:a", "192k"]
    if media_type == "video" and suffix == ".avi":
        return ["-c:a", "libmp3lame", "-b:a", "192k"]
    if media_type == "video" and suffix in {".mpeg", ".mpg"}:
        return ["-c:a", "mp2", "-b:a", "192k"]
    return ["-c:a", "aac", "-b:a", "192k"]


def build_ffmpeg_command(
    ffmpeg_path: str,
    input_path: Path,
    output_path: Path,
    audio_filter: str,
) -> list[str]:
    kind = media_kind(input_path)
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(input_path),
    ]

    if kind == "video":
        command.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-map",
                "0:s?",
                "-map_metadata",
                "0",
                "-c:v",
                "copy",
                "-c:s",
                "copy",
            ]
        )
    else:
        command.extend(["-map", "0:a:0", "-vn", "-map_metadata", "0"])

    command.extend(["-af", audio_filter])
    command.extend(_audio_codec_args(output_path, kind))
    command.append(str(output_path))
    return command


def process_media(
    input_path: Path,
    output_path: Path,
    preset_name: str = "balanced",
    reduction: float | None = None,
    noise_floor: float | None = None,
    force: bool = False,
    ffmpeg_path: str | None = None,
    dry_run: bool = False,
) -> list[str]:
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()

    if not input_path.is_file():
        raise DenoiseError(f"File input tidak ditemukan: {input_path}")
    input_kind = media_kind(input_path)
    output_kind = media_kind(output_path)
    if input_kind != output_kind:
        raise DenoiseError(
            "Jenis file input dan output harus sama-sama audio atau sama-sama video."
        )
    if input_path == output_path:
        raise DenoiseError("File input dan output tidak boleh sama.")
    if output_path.exists() and not force:
        raise DenoiseError(
            f"File output sudah ada: {output_path}. Gunakan --force untuk menimpanya."
        )

    resolved_ffmpeg = resolve_ffmpeg(ffmpeg_path)
    audio_filter = denoise_filter(preset_name, reduction, noise_floor)
    temp_output = output_path.with_name(
        f".{output_path.stem}.{uuid4().hex}.tmp{output_path.suffix}"
    )
    command = build_ffmpeg_command(
        resolved_ffmpeg, input_path, temp_output, audio_filter
    )
    if dry_run:
        return command

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise DenoiseError(
                f"FFmpeg gagal memproses media (kode {completed.returncode})."
            )
        if not temp_output.is_file():
            raise DenoiseError("FFmpeg selesai tetapi tidak menghasilkan file output.")
        temp_output.replace(output_path)
    except OSError as exc:
        raise DenoiseError(f"Tidak dapat menjalankan FFmpeg: {exc}") from exc
    finally:
        if temp_output.exists():
            temp_output.unlink()

    return command
