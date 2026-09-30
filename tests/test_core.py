import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from denoise_cli.core import (
    DenoiseError,
    MediaInfo,
    _parse_progress_seconds,
    _run_ffmpeg,
    build_ffmpeg_command,
    default_output_path,
    denoise_filter,
    media_kind,
    parse_probe_output,
    process_media,
    select_tracks,
)


AUDIO_INFO = MediaInfo(duration=1.0, audio_tracks=("pcm_s16le, 48000 Hz, mono",))


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

    def test_video_command_processes_selected_tracks_and_copies_others(self):
        command = build_ffmpeg_command(
            "ffmpeg",
            Path("input.mkv"),
            Path("output.mkv"),
            "afftdn=nr=14",
            audio_track_count=3,
            tracks=[1],
        )
        self.assertIn("0:a", command)
        self.assertEqual(command[command.index("-c:a:0") + 1], "copy")
        self.assertEqual(command[command.index("-filter:a:1") + 1], "afftdn=nr=14")
        self.assertEqual(command[command.index("-c:a:1") + 1], "aac")
        self.assertEqual(command[command.index("-b:a:1") + 1], "192k")
        self.assertEqual(command[command.index("-c:a:2") + 1], "copy")
        self.assertNotIn("-filter:a:0", command)

    def test_audio_command_maps_selected_track(self):
        command = build_ffmpeg_command(
            "ffmpeg",
            Path("input.m4a"),
            Path("output.m4a"),
            "afftdn=nr=14",
            audio_track_count=2,
            tracks=[1],
        )
        self.assertEqual(command[command.index("-map") + 1], "0:a:1")

    def test_select_tracks_defaults(self):
        self.assertEqual(select_tracks("video", 3, None), [0, 1, 2])
        self.assertEqual(select_tracks("audio", 3, None), [0])
        self.assertEqual(select_tracks("video", 3, [3, 1, 3]), [0, 2])

    def test_select_tracks_validation(self):
        with self.assertRaisesRegex(DenoiseError, "tidak memiliki track audio"):
            select_tracks("video", 0, None)
        with self.assertRaisesRegex(DenoiseError, "Track audio 4 tidak ada"):
            select_tracks("video", 3, [4])
        with self.assertRaisesRegex(DenoiseError, "Track audio 0 tidak ada"):
            select_tracks("video", 3, [0])
        with self.assertRaisesRegex(DenoiseError, "satu track"):
            select_tracks("audio", 2, [1, 2])

    def test_parse_probe_output(self):
        stderr = (
            "Input #0, matroska,webm, from 'multi.mkv':\n"
            "  Duration: 00:01:05.50, start: 0.000000, bitrate: 179 kb/s\n"
            "  Stream #0:0: Video: h264 (High), yuv420p, 160x120, 25 fps\n"
            "  Stream #0:1(eng): Audio: aac (LC), 44100 Hz, stereo, fltp (default)\n"
            "  Stream #0:2[0x2](ind): Audio: opus, 48000 Hz, mono, fltp\n"
            "  Stream #0:3: Subtitle: subrip\n"
            "At least one output file must be specified\n"
        )
        info = parse_probe_output(stderr)
        self.assertAlmostEqual(info.duration, 65.5)
        self.assertEqual(len(info.audio_tracks), 2)
        self.assertTrue(info.audio_tracks[0].startswith("aac (LC)"))
        self.assertTrue(info.audio_tracks[1].startswith("opus"))

    def test_parse_probe_output_rejects_unreadable_media(self):
        stderr = "input.wav: Invalid data found when processing input\n"
        with self.assertRaisesRegex(DenoiseError, "Invalid data"):
            parse_probe_output(stderr)

    def test_rnnoise_filter_escapes_model_path(self):
        with TemporaryDirectory() as directory:
            model = Path(directory) / "model, [x]'s.rnnn"
            model.write_bytes(b"model")
            audio_filter = denoise_filter("balanced", engine="rnnoise", model_path=model)

        self.assertTrue(audio_filter.startswith("arnndn=m="))
        self.assertIn("\\,", audio_filter)
        self.assertIn("\\[x\\]", audio_filter)
        self.assertIn("\\\\\\'s", audio_filter)
        if model.drive:
            self.assertIn(f"{model.drive[0]}\\\\:", audio_filter)

    def test_rnnoise_requires_existing_model(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(DenoiseError, "membutuhkan file model"):
                denoise_filter("balanced", engine="rnnoise")
        with self.assertRaisesRegex(DenoiseError, "tidak ditemukan"):
            denoise_filter("balanced", engine="rnnoise", model_path="tidak-ada.rnnn")

    def test_rnnoise_rejects_spectral_options(self):
        with self.assertRaisesRegex(DenoiseError, "engine spectral"):
            denoise_filter("balanced", reduction=10, engine="rnnoise")

    def test_parse_progress_seconds(self):
        self.assertEqual(_parse_progress_seconds("out_time_us=2500000\n"), 2.5)
        self.assertEqual(_parse_progress_seconds("out_time_ms=1000000"), 1.0)
        self.assertIsNone(_parse_progress_seconds("out_time_us=N/A"))
        self.assertIsNone(_parse_progress_seconds("frame=10"))

    def test_run_ffmpeg_reports_progress(self):
        class FakePopen:
            def __init__(self, command, **_kwargs):
                self.command = command
                self.stdout = StringIO(
                    "out_time_us=N/A\nout_time_us=1000000\n"
                    "out_time_us=2000000\nprogress=end\n"
                )
                self.stderr = StringIO("")

            def wait(self):
                return 0

            def kill(self):
                pass

        reported = []
        with patch("denoise_cli.core.subprocess.Popen", FakePopen):
            returncode, stderr = _run_ffmpeg(
                ["ffmpeg", "-i", "in.wav", "out.wav"], 4.0, reported.append
            )

        self.assertEqual(returncode, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(reported, [0.25, 0.5, 1.0])

    def test_process_media_reports_ffmpeg_stderr_and_cleans_temp_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.wav"
            output = root / "output.wav"
            source.write_bytes(b"not-real-audio")

            with (
                patch("denoise_cli.core.resolve_ffmpeg", return_value="ffmpeg"),
                patch("denoise_cli.core.probe_media", return_value=AUDIO_INFO),
                patch(
                    "denoise_cli.core._run_ffmpeg",
                    return_value=(1, "detail kegagalan ffmpeg"),
                ),
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

            def create_temp_output(command, *_args):
                Path(command[-1]).write_bytes(b"processed")
                return 0, ""

            with (
                patch("denoise_cli.core.resolve_ffmpeg", return_value="ffmpeg"),
                patch("denoise_cli.core.probe_media", return_value=AUDIO_INFO),
                patch("denoise_cli.core._run_ffmpeg", side_effect=create_temp_output),
            ):
                process_media(source, output)

            self.assertEqual(output.read_bytes(), b"processed")
            self.assertEqual(list(output.parent.glob(".*.tmp.wav")), [])

    def test_process_media_rejects_video_without_audio(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.mp4"
            source.write_bytes(b"video")

            with (
                patch("denoise_cli.core.resolve_ffmpeg", return_value="ffmpeg"),
                patch(
                    "denoise_cli.core.probe_media",
                    return_value=MediaInfo(duration=2.0, audio_tracks=()),
                ),
            ):
                with self.assertRaisesRegex(DenoiseError, "tidak memiliki track"):
                    process_media(source, root / "output.mp4")


if __name__ == "__main__":
    unittest.main()
