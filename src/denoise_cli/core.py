from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from denoise_cli import deepfilter


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

ENGINES = ("deepfilter", "rnnoise", "spectral")
DEFAULT_ENGINE = "deepfilter"

# Cegah jendela konsol FFmpeg muncul saat dipanggil dari aplikasi GUI di Windows.
_SUBPROCESS_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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


@dataclass(frozen=True)
class MediaInfo:
    duration: float | None
    audio_tracks: tuple[str, ...]


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


def _matching_media_kind(input_path: Path, output_path: Path) -> str:
    input_kind = media_kind(input_path)
    output_kind = media_kind(output_path)
    if input_kind != output_kind:
        raise DenoiseError(
            "Jenis file input dan output harus sama-sama audio atau sama-sama video."
        )
    if (
        input_kind == "video"
        and input_path.suffix.lower() != output_path.suffix.lower()
    ):
        raise DenoiseError(
            "Ekstensi output video harus sama dengan input karena stream video "
            "disalin tanpa encode ulang."
        )
    return input_kind


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


_DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
_STREAM_PATTERN = re.compile(r"Stream #0:(\d+)\S*:\s*(\w+):\s*(.*)")


def parse_probe_output(stderr: str) -> MediaInfo:
    """Baca durasi dan daftar track audio dari keluaran `ffmpeg -i`."""
    if "Input #0" not in stderr:
        lines = [line.strip() for line in stderr.splitlines() if line.strip()]
        detail = lines[-1] if lines else "keluaran FFmpeg kosong"
        raise DenoiseError(f"File tidak dapat dibaca sebagai media: {detail}")

    duration = None
    match = _DURATION_PATTERN.search(stderr)
    if match:
        hours, minutes, seconds = match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    seen: set[int] = set()
    audio_tracks: list[str] = []
    for stream in _STREAM_PATTERN.finditer(stderr):
        index = int(stream.group(1))
        if index in seen:
            continue
        seen.add(index)
        if stream.group(2) == "Audio":
            audio_tracks.append(stream.group(3).strip())
    return MediaInfo(duration=duration or None, audio_tracks=tuple(audio_tracks))


def probe_media(ffmpeg_path: str, input_path: Path) -> MediaInfo:
    try:
        completed = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-nostdin", "-i", str(input_path)],
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_SUBPROCESS_FLAGS,
        )
    except OSError as exc:
        raise DenoiseError(f"Tidak dapat menjalankan FFmpeg: {exc}") from exc
    return parse_probe_output(completed.stderr or "")


def _escape_filter_value(value: str) -> str:
    # Nilai opsi di-escape dua kali: sekali untuk parser opsi filter, sekali
    # untuk parser filtergraph, sesuai aturan escaping FFmpeg.
    option_level = "".join(f"\\{c}" if c in "\\':" else c for c in value)
    return "".join(f"\\{c}" if c in "\\'[],;" else c for c in option_level)


def resolve_rnnoise_model(model_path: str | os.PathLike[str] | None) -> Path:
    configured = model_path or os.environ.get("DENOISE_RNNOISE_MODEL")
    if not configured:
        raise DenoiseError(
            "Engine rnnoise membutuhkan file model .rnnn. Berikan lokasinya "
            "melalui --model atau environment variable DENOISE_RNNOISE_MODEL."
        )
    candidate = Path(configured).expanduser()
    if not candidate.is_file():
        raise DenoiseError(f"File model RNNoise tidak ditemukan: {candidate}")
    return candidate.resolve()


def denoise_filter(
    preset_name: str,
    reduction: float | None = None,
    noise_floor: float | None = None,
    engine: str = "spectral",
    model_path: str | os.PathLike[str] | None = None,
) -> str:
    if engine == "rnnoise":
        if reduction is not None or noise_floor is not None:
            raise DenoiseError(
                "--reduction dan --noise-floor hanya berlaku untuk engine spectral."
            )
        model = resolve_rnnoise_model(model_path)
        return f"arnndn=m={_escape_filter_value(model.as_posix())}"
    if engine != "spectral":
        choices = ", ".join(ENGINES)
        raise DenoiseError(
            f"Engine '{engine}' tidak dikenal. Pilihan yang tersedia: {choices}."
        )

    try:
        preset = PRESETS[preset_name]
    except KeyError as exc:
        choices = ", ".join(PRESETS)
        raise DenoiseError(
            f"Preset '{preset_name}' tidak dikenal. Pilihan yang tersedia: {choices}."
        ) from exc
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


def select_tracks(
    kind: str, track_count: int, requested: Sequence[int] | None
) -> list[int]:
    """Kembalikan indeks track audio (mulai 0) yang akan diproses."""
    if track_count == 0:
        subject = "Video" if kind == "video" else "File"
        raise DenoiseError(f"{subject} tidak memiliki track audio untuk diproses.")
    if not requested:
        return list(range(track_count)) if kind == "video" else [0]

    selected = sorted(set(requested))
    for track in selected:
        if not 1 <= track <= track_count:
            raise DenoiseError(
                f"Track audio {track} tidak ada. File ini memiliki "
                f"{track_count} track audio (nomor 1 sampai {track_count})."
            )
    if kind == "audio" and len(selected) > 1:
        raise DenoiseError(
            "Output audio hanya dapat berisi satu track. Pilih satu --track, "
            "atau gunakan output video untuk memproses beberapa track."
        )
    return [track - 1 for track in selected]


def _audio_codec_args(
    output_path: Path, media_type: str, stream: int | None = None
) -> list[str]:
    suffix = output_path.suffix.lower()
    if suffix == ".wav":
        args = ["-c:a", "pcm_s16le"]
    elif suffix == ".flac":
        args = ["-c:a", "flac"]
    elif suffix == ".mp3":
        args = ["-c:a", "libmp3lame", "-b:a", "192k"]
    elif suffix in {".ogg", ".oga"}:
        args = ["-c:a", "libvorbis", "-q:a", "5"]
    elif suffix == ".opus" or (media_type == "video" and suffix == ".webm"):
        args = ["-c:a", "libopus", "-b:a", "160k"]
    elif suffix == ".wma":
        args = ["-c:a", "wmav2", "-b:a", "192k"]
    elif media_type == "video" and suffix == ".avi":
        args = ["-c:a", "libmp3lame", "-b:a", "192k"]
    elif media_type == "video" and suffix in {".mpeg", ".mpg"}:
        args = ["-c:a", "mp2", "-b:a", "192k"]
    else:
        args = ["-c:a", "aac", "-b:a", "192k"]

    if stream is None:
        return args
    return [f"{arg}:{stream}" if arg.startswith("-") else arg for arg in args]


def build_ffmpeg_command(
    ffmpeg_path: str,
    input_path: Path,
    output_path: Path,
    audio_filter: str,
    audio_track_count: int = 1,
    tracks: Sequence[int] | None = None,
) -> list[str]:
    """Susun command FFmpeg. `tracks` berisi indeks track audio mulai dari 0."""
    kind = _matching_media_kind(input_path, output_path)
    if tracks is None:
        tracks = list(range(audio_track_count)) if kind == "video" else [0]

    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(input_path),
    ]

    if kind == "video":
        # Semua track audio dipertahankan; track yang tidak dipilih disalin apa adanya.
        command.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                "0:a",
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
        for stream in range(audio_track_count):
            if stream in tracks:
                command.extend([f"-filter:a:{stream}", audio_filter])
                command.extend(_audio_codec_args(output_path, kind, stream))
            else:
                command.extend([f"-c:a:{stream}", "copy"])
    else:
        command.extend(["-map", f"0:a:{tracks[0]}", "-vn", "-map_metadata", "0"])
        command.extend(["-af", audio_filter])
        command.extend(_audio_codec_args(output_path, kind))

    command.append(str(output_path))
    return command


def _parse_progress_seconds(line: str) -> float | None:
    key, _, value = line.strip().partition("=")
    if key not in {"out_time_us", "out_time_ms"}:
        return None
    try:
        # FFmpeg memakai mikrodetik untuk kedua kunci ini.
        return max(int(value), 0) / 1_000_000
    except ValueError:
        return None


def _run_ffmpeg(
    command: list[str],
    duration: float | None = None,
    on_progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
) -> tuple[int, str]:
    """Jalankan FFmpeg dan laporkan progres (0.0 sampai 1.0) bila memungkinkan.

    Jika `cancel` di-set, FFmpeg dihentikan dan DenoiseError dilempar.
    """
    full_command = [command[0], "-nostats", "-progress", "pipe:1", *command[1:]]
    process = subprocess.Popen(
        full_command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
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
    try:
        for line in process.stdout:
            if cancel is not None and cancel.is_set():
                raise DenoiseError("Proses dibatalkan.")
            if on_progress is None:
                continue
            if line.strip() == "progress=end":
                on_progress(1.0)
                continue
            seconds = _parse_progress_seconds(line)
            if seconds is not None and duration:
                on_progress(min(seconds / duration, 1.0))
        returncode = process.wait()
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        reader.join(timeout=5)
    return returncode, "".join(stderr_chunks)


def build_extract_command(
    ffmpeg_path: str, input_path: Path, tracks: Sequence[int], work_dir: Path
) -> list[str]:
    """Ekstrak track audio terpilih ke WAV 48 kHz (format masukan DeepFilterNet)."""
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(input_path),
    ]
    for track in tracks:
        command.extend(
            [
                "-map",
                f"0:a:{track}",
                "-vn",
                "-ar",
                "48000",
                "-c:a",
                "pcm_s16le",
                str(work_dir / f"track{track}.wav"),
            ]
        )
    return command


def build_remux_command(
    ffmpeg_path: str,
    input_path: Path,
    output_path: Path,
    processed: dict[int, Path],
    audio_track_count: int,
) -> list[str]:
    """Gabungkan audio hasil DeepFilterNet kembali ke container output.

    `processed` memetakan indeks track audio (mulai 0) ke file WAV hasil proses.
    """
    kind = _matching_media_kind(input_path, output_path)
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(input_path),
    ]
    order = sorted(processed)
    for track in order:
        command.extend(["-i", str(processed[track])])
    input_index = {track: position + 1 for position, track in enumerate(order)}

    if kind == "audio":
        command.extend(["-map", f"{input_index[order[0]]}:a:0", "-map_metadata", "0"])
        command.extend(_audio_codec_args(output_path, kind))
        command.append(str(output_path))
        return command

    command.extend(["-map", "0:v:0"])
    for stream in range(audio_track_count):
        if stream in processed:
            command.extend(["-map", f"{input_index[stream]}:a:0"])
        else:
            command.extend(["-map", f"0:a:{stream}"])
    command.extend(
        ["-map", "0:s?", "-map_metadata", "0", "-c:v", "copy", "-c:s", "copy"]
    )
    for stream in range(audio_track_count):
        if stream in processed:
            # Pertahankan metadata track (bahasa, judul) dari track aslinya.
            command.extend([f"-map_metadata:s:a:{stream}", f"0:s:a:{stream}"])
            command.extend(_audio_codec_args(output_path, kind, stream))
        else:
            command.extend([f"-c:a:{stream}", "copy"])
    command.append(str(output_path))
    return command


def _check_ffmpeg(returncode: int, stderr: str) -> None:
    if returncode == 0:
        return
    details = stderr.strip()
    if details:
        lines = [line.strip() for line in details.splitlines() if line.strip()]
        summary = "\n".join(lines[-8:])
        if len(summary) > 2000:
            summary = f"…{summary[-1999:]}"
        raise DenoiseError(f"FFmpeg gagal memproses media:\n{summary}")
    raise DenoiseError(f"FFmpeg gagal memproses media (kode {returncode}).")


def _stage(
    on_progress: Callable[[float], None] | None, start: float, end: float
) -> Callable[[float], None] | None:
    """Petakan progres satu tahap (0..1) ke rentang [start, end] progres total."""
    if on_progress is None:
        return None
    return lambda fraction: on_progress(start + (end - start) * fraction)


def _run_deepfilter_pipeline(
    ffmpeg_path: str,
    input_path: Path,
    temp_output: Path,
    info: MediaInfo,
    selected: list[int],
    preset_name: str,
    dry_run: bool,
    on_progress: Callable[[float], None] | None,
    on_status: Callable[[str], None] | None,
    cancel: threading.Event | None,
) -> list[list[str]]:
    """Ekstrak audio -> DeepFilterNet -> gabungkan kembali ke output sementara."""
    status = on_status or (lambda _message: None)
    try:
        binary = deepfilter.resolve_binary(
            allow_download=not dry_run,
            on_status=status,
            on_progress=_stage(on_progress, 0.0, 0.05),
            cancel=cancel,
        )
        with tempfile.TemporaryDirectory(prefix="denoise-") as work:
            work_dir = Path(work)
            out_dir = work_dir / "out"
            processed = {track: out_dir / f"track{track}.wav" for track in selected}
            extract = build_extract_command(ffmpeg_path, input_path, selected, work_dir)
            filter_command = deepfilter.build_command(
                binary or deepfilter.binary_name(),
                [work_dir / f"track{track}.wav" for track in selected],
                out_dir,
                preset_name,
            )
            remux = build_remux_command(
                ffmpeg_path, input_path, temp_output, processed, len(info.audio_tracks)
            )
            commands = [extract, filter_command, remux]
            if dry_run:
                return commands

            status("Menyiapkan audio...")
            _check_ffmpeg(
                *_run_ffmpeg(
                    extract, info.duration, _stage(on_progress, 0.05, 0.15), cancel
                )
            )
            status("Membersihkan noise dengan AI...")
            deepfilter.run(
                filter_command,
                (info.duration or 60.0) * len(selected),
                _stage(on_progress, 0.15, 0.85),
                cancel,
            )
            if not all(path.is_file() for path in processed.values()):
                raise DenoiseError("DeepFilterNet selesai tetapi tidak menghasilkan audio.")
            status("Menyimpan hasil...")
            _check_ffmpeg(
                *_run_ffmpeg(remux, info.duration, _stage(on_progress, 0.85, 1.0), cancel)
            )
            return commands
    except deepfilter.DeepFilterError as exc:
        raise DenoiseError(str(exc)) from exc


def process_media(
    input_path: Path,
    output_path: Path,
    preset_name: str = "balanced",
    reduction: float | None = None,
    noise_floor: float | None = None,
    force: bool = False,
    ffmpeg_path: str | None = None,
    dry_run: bool = False,
    engine: str = DEFAULT_ENGINE,
    model_path: str | os.PathLike[str] | None = None,
    tracks: Sequence[int] | None = None,
    on_progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
    on_status: Callable[[str], None] | None = None,
) -> list[list[str]]:
    """Proses media dan kembalikan daftar command yang (akan) dijalankan.

    `tracks` berisi nomor track audio mulai dari 1.
    """
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()

    if not input_path.is_file():
        raise DenoiseError(f"File input tidak ditemukan: {input_path}")
    kind = _matching_media_kind(input_path, output_path)
    if input_path == output_path:
        raise DenoiseError("File input dan output tidak boleh sama.")
    if output_path.exists() and not force:
        raise DenoiseError(
            f"File output sudah ada: {output_path}. Gunakan --force untuk menimpanya."
        )

    if engine == "deepfilter":
        if reduction is not None or noise_floor is not None:
            raise DenoiseError(
                "--reduction dan --noise-floor hanya berlaku untuk engine spectral."
            )
        if preset_name not in deepfilter.PRESET_ARGS:
            raise DenoiseError(
                f"Preset '{preset_name}' tidak dikenal. Pilihan yang tersedia: "
                f"{', '.join(deepfilter.PRESET_ARGS)}."
            )
        audio_filter = None
    else:
        audio_filter = denoise_filter(
            preset_name, reduction, noise_floor, engine=engine, model_path=model_path
        )
    resolved_ffmpeg = resolve_ffmpeg(ffmpeg_path)
    info = probe_media(resolved_ffmpeg, input_path)
    selected = select_tracks(kind, len(info.audio_tracks), tracks)

    temp_output = output_path.with_name(
        f".{output_path.stem}.{uuid4().hex}.tmp{output_path.suffix}"
    )
    try:
        if not dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        if audio_filter is None:
            commands = _run_deepfilter_pipeline(
                resolved_ffmpeg,
                input_path,
                temp_output,
                info,
                selected,
                preset_name,
                dry_run,
                on_progress,
                on_status,
                cancel,
            )
        else:
            command = build_ffmpeg_command(
                resolved_ffmpeg,
                input_path,
                temp_output,
                audio_filter,
                audio_track_count=len(info.audio_tracks),
                tracks=selected,
            )
            commands = [command]
            if not dry_run:
                if on_status:
                    on_status("Membersihkan noise...")
                _check_ffmpeg(*_run_ffmpeg(command, info.duration, on_progress, cancel))
        if dry_run:
            return commands
        if not temp_output.is_file():
            raise DenoiseError("FFmpeg selesai tetapi tidak menghasilkan file output.")
        temp_output.replace(output_path)
    except OSError as exc:
        raise DenoiseError(f"Tidak dapat menjalankan proses: {exc}") from exc
    finally:
        try:
            temp_output.unlink(missing_ok=True)
        except OSError:
            # Jangan menutupi penyebab kegagalan utama jika file sementara terkunci.
            pass

    return commands

