from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from denoise_cli import __version__
from denoise_cli.core import (
    DEFAULT_ENGINE,
    ENGINES,
    PRESETS,
    DenoiseError,
    default_output_path,
    probe_media,
    process_media,
    resolve_ffmpeg,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="denoise",
        description="Kurangi noise pada audio atau track suara video secara lokal.",
    )
    parser.add_argument("input", type=Path, help="file audio atau video sumber")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="lokasi output (default: <nama>.denoised.<ekstensi>)",
    )
    parser.add_argument(
        "-e",
        "--engine",
        choices=ENGINES,
        default=DEFAULT_ENGINE,
        help=(
            "metode denoise: deepfilter (AI DeepFilterNet, terbaik untuk ucapan; "
            "diunduh otomatis saat pertama dipakai), rnnoise (neural ringan, butuh "
            "--model), atau spectral (FFT, untuk desis stabil/musik) "
            f"(default: {DEFAULT_ENGINE})"
        ),
    )
    parser.add_argument(
        "-m",
        "--model",
        metavar="PATH",
        help="file model .rnnn untuk engine rnnoise (atau DENOISE_RNNOISE_MODEL)",
    )
    parser.add_argument(
        "-p",
        "--preset",
        choices=tuple(PRESETS),
        default="balanced",
        help="kekuatan denoise untuk engine deepfilter/spectral (default: balanced)",
    )
    parser.add_argument(
        "--reduction",
        type=float,
        metavar="DB",
        help="atur pengurangan noise secara manual, 0.01 sampai 97",
    )
    parser.add_argument(
        "--noise-floor",
        type=float,
        metavar="DB",
        help="perkiraan noise floor, -80 sampai -20 dB",
    )
    parser.add_argument(
        "-t",
        "--track",
        type=int,
        action="append",
        metavar="N",
        help=(
            "nomor track audio yang diproses, mulai dari 1; ulangi untuk beberapa "
            "track (default video: semua track, audio: track pertama)"
        ),
    )
    parser.add_argument(
        "--list-tracks",
        action="store_true",
        help="tampilkan daftar track audio pada input lalu keluar",
    )
    parser.add_argument(
        "--ffmpeg",
        metavar="PATH",
        help="gunakan executable FFmpeg tertentu",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="timpa file output jika sudah ada",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="jangan tampilkan indikator progres",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="tampilkan command FFmpeg tanpa memproses file",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


class ProgressPrinter:
    """Tampilkan persentase progres pada satu baris di stderr."""

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stderr
        self.last_percent = -1
        self.label = "Memproses..."
        self.width = 0

    def __call__(self, fraction: float) -> None:
        percent = int(fraction * 100)
        if percent == self.last_percent:
            return
        self.last_percent = percent
        self._draw()

    def status(self, message: str) -> None:
        self.label = message
        self._draw()

    def _draw(self) -> None:
        percent = max(self.last_percent, 0)
        filled = percent // 5
        bar = "#" * filled + "-" * (20 - filled)
        line = f"[{bar}] {percent:3d}%  {self.label}"
        # Tutup sisa teks baris sebelumnya yang lebih panjang.
        padding = " " * max(self.width - len(line), 0)
        self.width = len(line)
        self.stream.write(f"\r{line}{padding}")
        self.stream.flush()

    def finish(self) -> None:
        if self.last_percent >= 0:
            self.stream.write("\n")
            self.stream.flush()


def list_tracks(input_path: Path, ffmpeg_path: str | None) -> int:
    input_path = input_path.expanduser().resolve()
    if not input_path.is_file():
        raise DenoiseError(f"File input tidak ditemukan: {input_path}")
    info = probe_media(resolve_ffmpeg(ffmpeg_path), input_path)
    if not info.audio_tracks:
        print("Tidak ada track audio.")
        return 0
    for number, description in enumerate(info.audio_tracks, start=1):
        print(f"{number}: {description}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output or default_output_path(args.input)

    show_progress = not (args.quiet or args.dry_run) and sys.stderr.isatty()
    progress = ProgressPrinter() if show_progress else None
    if progress:
        on_status = progress.status
    elif not (args.quiet or args.dry_run):
        on_status = lambda message: print(message, file=sys.stderr)  # noqa: E731
    else:
        on_status = None

    try:
        if args.list_tracks:
            return list_tracks(args.input, args.ffmpeg)
        commands = process_media(
            input_path=args.input,
            output_path=output,
            preset_name=args.preset,
            reduction=args.reduction,
            noise_floor=args.noise_floor,
            force=args.force,
            ffmpeg_path=args.ffmpeg,
            dry_run=args.dry_run,
            engine=args.engine,
            model_path=args.model,
            tracks=args.track,
            on_progress=progress,
            on_status=on_status,
        )
    except DenoiseError as exc:
        if progress:
            progress.finish()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        if progress:
            progress.finish()
        print("Dibatalkan.", file=sys.stderr)
        return 130

    if progress:
        progress.finish()
    if args.dry_run:
        for command in commands:
            print(subprocess.list2cmdline(command))
    else:
        print(f"Selesai: {output.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
