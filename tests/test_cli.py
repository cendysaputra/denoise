import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from denoise_cli.cli import main
from denoise_cli.core import DenoiseError


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


if __name__ == "__main__":
    unittest.main()
