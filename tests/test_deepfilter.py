import hashlib
import threading
import unittest
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from denoise_cli import deepfilter
from denoise_cli.core import (
    DenoiseError,
    MediaInfo,
    build_extract_command,
    build_remux_command,
    process_media,
)


class FakeResponse(BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class DeepFilterBinaryTests(unittest.TestCase):
    def test_build_command_uses_preset_arguments(self):
        inputs = [Path("a.wav"), Path("b.wav")]
        light = deepfilter.build_command("df", inputs, Path("out"), "light")
        strong = deepfilter.build_command("df", inputs, Path("out"), "strong")
        balanced = deepfilter.build_command("df", inputs, Path("out"), "balanced")

        self.assertEqual(light[light.index("--atten-lim-db") + 1], "20")
        self.assertIn("--pf", strong)
        self.assertNotIn("--pf", balanced)
        self.assertNotIn("--atten-lim-db", balanced)
        self.assertIn("--compensate-delay", balanced)
        self.assertEqual(balanced[-2:], ["a.wav", "b.wav"])
        with self.assertRaises(deepfilter.DeepFilterError):
            deepfilter.build_command("df", inputs, Path("out"), "extreme")

    def test_resolve_prefers_environment_variable(self):
        with TemporaryDirectory() as directory:
            binary = Path(directory) / "deep-filter.exe"
            binary.write_bytes(b"bin")
            with patch.dict("os.environ", {"DENOISE_DEEPFILTER": str(binary)}):
                self.assertEqual(deepfilter.resolve_binary(), binary.resolve())
            with patch.dict("os.environ", {"DENOISE_DEEPFILTER": str(binary) + ".x"}):
                with self.assertRaisesRegex(deepfilter.DeepFilterError, "tidak ditemukan"):
                    deepfilter.resolve_binary()

    def test_resolve_uses_cache_and_skips_download_when_not_allowed(self):
        with TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            cache = Path(directory)
            with patch("denoise_cli.deepfilter.cache_dir", return_value=cache):
                self.assertIsNone(deepfilter.resolve_binary(allow_download=False))
                cached = cache / deepfilter.binary_name()
                cached.write_bytes(b"bin")
                self.assertEqual(deepfilter.resolve_binary(allow_download=False), cached)

    def test_download_verifies_checksum(self):
        payload = b"deep-filter-binary"
        good = ("deep-filter.exe", hashlib.sha256(payload).hexdigest())
        bad = ("deep-filter.exe", "0" * 64)

        with TemporaryDirectory() as directory:
            destination = Path(directory) / "bin" / "deep-filter.exe"
            reported = []
            with (
                patch("denoise_cli.deepfilter._asset", return_value=good),
                patch(
                    "denoise_cli.deepfilter.urllib.request.urlopen",
                    return_value=FakeResponse(payload),
                ),
            ):
                deepfilter.download(destination, reported.append)
            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(reported[-1], 1.0)

            destination.unlink()
            with (
                patch("denoise_cli.deepfilter._asset", return_value=bad),
                patch(
                    "denoise_cli.deepfilter.urllib.request.urlopen",
                    return_value=FakeResponse(payload),
                ),
            ):
                with self.assertRaisesRegex(deepfilter.DeepFilterError, "checksum"):
                    deepfilter.download(destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.iterdir()), [])

    def test_unsupported_platform_has_clear_error(self):
        with (
            patch("denoise_cli.deepfilter.sys.platform", "sunos5"),
            patch("denoise_cli.deepfilter.platform.machine", return_value="sparc"),
        ):
            with self.assertRaisesRegex(deepfilter.DeepFilterError, "belum tersedia"):
                deepfilter.binary_name()

    def test_run_reports_failure_output(self):
        class FailingPopen:
            def __init__(self, *_args, **_kwargs):
                self.stderr = StringIO("model error\n")

            def wait(self, timeout=None):
                return 3

            def kill(self):
                pass

        with patch("denoise_cli.deepfilter.subprocess.Popen", FailingPopen):
            with self.assertRaisesRegex(deepfilter.DeepFilterError, "model error"):
                deepfilter.run(["df"], 10.0)

    def test_run_stops_when_cancelled(self):
        killed = []

        class SlowPopen:
            def __init__(self, *_args, **_kwargs):
                self.stderr = StringIO("")

            def wait(self, timeout=None):
                if timeout is None:
                    return -9
                raise deepfilter.subprocess.TimeoutExpired("df", timeout)

            def kill(self):
                killed.append(True)

        cancel = threading.Event()
        cancel.set()
        with patch("denoise_cli.deepfilter.subprocess.Popen", SlowPopen):
            with self.assertRaisesRegex(deepfilter.DeepFilterError, "dibatalkan"):
                deepfilter.run(["df"], 10.0, None, cancel)
        self.assertEqual(killed, [True])


class DeepFilterPipelineTests(unittest.TestCase):
    def test_extract_command_writes_48k_wav_per_track(self):
        command = build_extract_command("ffmpeg", Path("in.mkv"), [0, 2], Path("w"))
        self.assertEqual(command.count("-map"), 2)
        self.assertIn("0:a:2", command)
        self.assertEqual(command[command.index("-ar") + 1], "48000")
        self.assertEqual(command[-1], str(Path("w") / "track2.wav"))

    def test_remux_replaces_processed_tracks_and_copies_the_rest(self):
        command = build_remux_command(
            "ffmpeg",
            Path("in.mkv"),
            Path("out.mkv"),
            {1: Path("t1.wav")},
            audio_track_count=3,
        )
        maps = [command[i + 1] for i, arg in enumerate(command) if arg == "-map"]
        self.assertEqual(maps, ["0:v:0", "0:a:0", "1:a:0", "0:a:2", "0:s?"])
        self.assertEqual(command[command.index("-c:a:0") + 1], "copy")
        self.assertEqual(command[command.index("-c:a:1") + 1], "aac")
        self.assertEqual(command[command.index("-c:a:2") + 1], "copy")
        self.assertEqual(command[command.index("-map_metadata:s:a:1") + 1], "0:s:a:1")

    def test_remux_audio_output(self):
        command = build_remux_command(
            "ffmpeg", Path("in.mp3"), Path("out.mp3"), {0: Path("t0.wav")}, 1
        )
        self.assertEqual(command[command.index("-map") + 1], "1:a:0")
        self.assertIn("libmp3lame", command)
        self.assertNotIn("0:v:0", command)

    def test_process_media_runs_full_pipeline(self):
        info = MediaInfo(duration=10.0, audio_tracks=("aac", "aac"))

        def fake_ffmpeg(command, _duration, on_progress, _cancel):
            # Tahap ekstrak dan remux sama-sama menulis ke argumen terakhir.
            for index, arg in enumerate(command):
                if arg.endswith(".wav") and command[index - 1] != "-i":
                    Path(arg).write_bytes(b"wav")
            Path(command[-1]).write_bytes(b"media")
            on_progress(1.0)
            return 0, ""

        def fake_deepfilter(command, _seconds, on_progress, _cancel):
            out_dir = Path(command[command.index("--output-dir") + 1])
            out_dir.mkdir()
            for arg in command:
                if arg.endswith(".wav"):
                    (out_dir / Path(arg).name).write_bytes(b"clean")
            on_progress(0.5)
            on_progress(1.0)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "film.mkv"
            output = root / "film.denoised.mkv"
            source.write_bytes(b"video")
            progress, statuses = [], []
            with (
                patch("denoise_cli.core.resolve_ffmpeg", return_value="ffmpeg"),
                patch("denoise_cli.core.probe_media", return_value=info),
                patch("denoise_cli.core.deepfilter.resolve_binary", return_value=Path("df")),
                patch("denoise_cli.core._run_ffmpeg", side_effect=fake_ffmpeg),
                patch("denoise_cli.core.deepfilter.run", side_effect=fake_deepfilter),
            ):
                commands = process_media(
                    source,
                    output,
                    on_progress=progress.append,
                    on_status=statuses.append,
                )

            self.assertEqual(output.read_bytes(), b"media")
            self.assertEqual(len(commands), 3)
            self.assertEqual(progress, sorted(progress))
            self.assertAlmostEqual(progress[-1], 1.0)
            self.assertIn("Membersihkan noise dengan AI...", statuses)
            self.assertEqual([p.name for p in root.iterdir()], ["film.denoised.mkv", "film.mkv"])

    def test_process_media_deepfilter_rejects_spectral_options(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "in.wav"
            source.write_bytes(b"audio")
            with self.assertRaisesRegex(DenoiseError, "engine spectral"):
                process_media(source, Path(directory) / "out.wav", reduction=10)

    def test_dry_run_does_not_download(self):
        info = MediaInfo(duration=1.0, audio_tracks=("pcm",))
        with TemporaryDirectory() as directory:
            source = Path(directory) / "in.wav"
            source.write_bytes(b"audio")
            with (
                patch("denoise_cli.core.resolve_ffmpeg", return_value="ffmpeg"),
                patch("denoise_cli.core.probe_media", return_value=info),
                patch(
                    "denoise_cli.core.deepfilter.resolve_binary", return_value=None
                ) as resolve,
                patch("denoise_cli.core._run_ffmpeg") as run_ffmpeg,
            ):
                commands = process_media(source, Path(directory) / "out.wav", dry_run=True)

        self.assertFalse(resolve.call_args.kwargs["allow_download"])
        run_ffmpeg.assert_not_called()
        self.assertEqual(commands[1][0], deepfilter.binary_name())


if __name__ == "__main__":
    unittest.main()
