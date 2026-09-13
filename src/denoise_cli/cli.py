from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from denoise_cli import __version__
from denoise_cli.core import DenoiseError, PRESETS, default_output_path, process_media


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
        "-p",
        "--preset",
        choices=tuple(PRESETS),
        default="balanced",
        help="kekuatan denoise (default: balanced)",
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
        "--dry-run",
        action="store_true",
        help="tampilkan command FFmpeg tanpa memproses file",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output or default_output_path(args.input)

    try:
        command = process_media(
            input_path=args.input,
            output_path=output,
            preset_name=args.preset,
            reduction=args.reduction,
            noise_floor=args.noise_floor,
            force=args.force,
            ffmpeg_path=args.ffmpeg,
            dry_run=args.dry_run,
        )
    except DenoiseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(subprocess.list2cmdline(command))
    else:
        print(f"Selesai: {output.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

