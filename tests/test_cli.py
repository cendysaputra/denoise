import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from denoise_cli.cli import ProgressPrinter, main
from denoise_cli.core import DenoiseError, MediaInfo


class CliTests(unittest.TestCase):
    def test_dry_run_prints_command(self):
        command = ["ffmpeg", "-i", "input.wav", "output.wav"]
        stdout = StringIO()

        with (
            patch("denoise_cli.cli.process_media", return_value=command),
            redirect_stdout(stdout),
        ):
            result = main(["input.wav", "--dry-run"])

        self.assertEqual(result, 0)
        self.assertIn("ffmpeg", stdout.getvalue())
        self.assertIn("output.wav", stdout.getvalue())

    def test_processing_error_is_written_to_stderr(self):
        stderr = StringIO()

        with (
            patch(
                "denoise_cli.cli.process_media",
                side_effect=DenoiseError("media tidak valid"),
            ),
            redirect_stderr(stderr),
        ):
            result = main(["input.wav"])

        self.assertEqual(result, 1)
        self.assertIn("Error: media tidak valid", stderr.getvalue())

    def test_options_are_forwarded_to_process_media(self):
        with (
            patch("denoise_cli.cli.process_media", return_value=[]) as process,
            redirect_stdout(StringIO()),
        ):
            result = main(
                [
                    "input.mkv",
                    "--engine",
                    "rnnoise",
                    "--model",
                    "model.rnnn",
                    "--track",
                    "2",
                    "-t",
                    "3",
                    "--quiet",
                ]
            )

        self.assertEqual(result, 0)
        kwargs = process.call_args.kwargs
        self.assertEqual(kwargs["engine"], "rnnoise")
        self.assertEqual(kwargs["model_path"], "model.rnnn")
        self.assertEqual(kwargs["tracks"], [2, 3])
        self.assertIsNone(kwargs["on_progress"])

    def test_list_tracks_prints_audio_tracks(self):
        stdout = StringIO()
        info = MediaInfo(duration=5.0, audio_tracks=("aac, stereo", "opus, mono"))

        with TemporaryDirectory() as directory:
            source = Path(directory) / "input.mkv"
            source.write_bytes(b"video")
            with (
                patch("denoise_cli.cli.resolve_ffmpeg", return_value="ffmpeg"),
                patch("denoise_cli.cli.probe_media", return_value=info),
                patch("denoise_cli.cli.process_media") as process,
                redirect_stdout(stdout),
            ):
                result = main([str(source), "--list-tracks"])

        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "1: aac, stereo\n2: opus, mono\n")
        process.assert_not_called()

    def test_keyboard_interrupt_returns_130(self):
        stderr = StringIO()

        with (
            patch("denoise_cli.cli.process_media", side_effect=KeyboardInterrupt),
            redirect_stderr(stderr),
        ):
            result = main(["input.wav"])

        self.assertEqual(result, 130)
        self.assertIn("Dibatalkan", stderr.getvalue())

    def test_progress_printer_writes_single_line(self):
        stream = StringIO()
        printer = ProgressPrinter(stream)

        printer(0.5)
        printer(0.5)
        printer(1.0)
        printer.finish()

        output = stream.getvalue()
        self.assertEqual(output.count("\r"), 2)
        self.assertIn(" 50%", output)
        self.assertTrue(output.endswith("100%\n"))


if __name__ == "__main__":
    unittest.main()
