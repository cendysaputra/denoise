import unittest
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import patch

from denoise_cli.core import (
    DenoiseError,
    build_ffmpeg_command,
    default_output_path,
    denoise_filter,
    media_kind,
    process_media,
)


class CoreTests(unittest.TestCase):
    def test_default_output_keeps_extension(self):
        source = Path("contoh.rekaman.wav")
        self.assertEqual(
            default_output_path(source), Path("contoh.rekaman.denoised.wav")
        )

    def test_media_kind(self):
        self.assertEqual(media_kind(Path("audio.MP3")), "audio")
        self.assertEqual(media_kind(Path("video.mp4")), "video")
        with self.assertRaises(DenoiseError):
            media_kind(Path("dokumen.txt"))

    def test_balanced_filter(self):
        self.assertEqual(
            denoise_filter("balanced"), "afftdn=nr=14:nf=-50:tn=1:gs=8"
        )

    def test_filter_validates_manual_values(self):
        with self.assertRaises(DenoiseError):
            denoise_filter("balanced", reduction=100)
        with self.assertRaises(DenoiseError):
            denoise_filter("balanced", noise_floor=-10)

    def test_filter_rejects_unknown_preset(self):
        with self.assertRaisesRegex(DenoiseError, "tidak dikenal"):
            denoise_filter("extreme")

    def test_video_command_copies_video_and_filters_audio(self):
        command = build_ffmpeg_command(
            "ffmpeg", Path("input.mp4"), Path("output.mp4"), "afftdn=nr=14"
        )
        self.assertIn("copy", command)
        self.assertIn("afftdn=nr=14", command)
        self.assertIn("aac", command)

    def test_avi_uses_compatible_audio_codec(self):
        command = build_ffmpeg_command(
            "ffmpeg", Path("input.avi"), Path("output.avi"), "afftdn=nr=14"
        )
        self.assertIn("libmp3lame", command)

    def test_mpeg_uses_compatible_audio_codec(self):
        command = build_ffmpeg_command(
            "ffmpeg", Path("input.mpg"), Path("output.mpg"), "afftdn=nr=14"
        )
        self.assertIn("mp2", command)

    def test_audio_command_uses_wav_codec(self):
        command = build_ffmpeg_command(
            "ffmpeg", Path("input.wav"), Path("output.wav"), "afftdn=nr=14"
        )
        self.assertIn("pcm_s16le", command)
        self.assertIn("-vn", command)

    def test_video_command_rejects_container_change(self):
        with self.assertRaisesRegex(DenoiseError, "Ekstensi output video"):
            build_ffmpeg_command(
                "ffmpeg", Path("input.mp4"), Path("output.webm"), "afftdn=nr=14"
            )

    def test_process_media_reports_ffmpeg_stderr_and_cleans_temp_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.wav"
            output = root / "output.wav"
            source.write_bytes(b"not-real-audio")

            failed = CompletedProcess(
                args=[], returncode=1, stdout="", stderr="detail kegagalan ffmpeg"
            )
            with (
                patch("denoise_cli.core.resolve_ffmpeg", return_value="ffmpeg"),
                patch("denoise_cli.core.subprocess.run", return_value=failed),
            ):
                with self.assertRaisesRegex(DenoiseError, "detail kegagalan ffmpeg"):
                    process_media(source, output)

            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".*.tmp.wav")), [])

    def test_process_media_atomically_moves_successful_output(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.wav"
            output = root / "nested" / "output.wav"
            source.write_bytes(b"source")

            def create_temp_output(command, **_kwargs):
                Path(command[-1]).write_bytes(b"processed")
                return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

            with (
                patch("denoise_cli.core.resolve_ffmpeg", return_value="ffmpeg"),
                patch(
                    "denoise_cli.core.subprocess.run", side_effect=create_temp_output
                ),
            ):
                process_media(source, output)

            self.assertEqual(output.read_bytes(), b"processed")
            self.assertEqual(list(output.parent.glob(".*.tmp.wav")), [])


if __name__ == "__main__":
    unittest.main()
