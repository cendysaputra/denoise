import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from denoise_cli.core import MediaInfo

try:
    import tkinter as tk

    from denoise_cli.gui import PRESET_LABELS, DenoiseApp

    _root = tk.Tk()
    _root.destroy()
    TK_AVAILABLE = True
except Exception:  # tkinter tidak terpasang atau tidak ada display
    TK_AVAILABLE = False


@unittest.skipUnless(TK_AVAILABLE, "Tk tidak tersedia di lingkungan ini")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = DenoiseApp(self.root)

    def tearDown(self):
        self.root.destroy()

    def wait_for(self, condition, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.02)
        self.fail("Kondisi tidak terpenuhi sebelum batas waktu.")

    def test_selecting_video_lists_all_tracks_checked(self):
        info = MediaInfo(duration=5.0, audio_tracks=("aac, stereo", "opus, mono"))
        with (
            patch("denoise_cli.gui.resolve_ffmpeg", return_value="ffmpeg"),
            patch("denoise_cli.gui.probe_media", return_value=info),
        ):
            self.app.set_input(Path("film.mkv"))
            self.wait_for(lambda: len(self.app.track_vars) == 2)

        self.assertEqual(self.app.selected_tracks(), [1, 2])
        self.assertEqual(Path(self.app.output_var.get()), Path("film.denoised.mkv"))

    def test_selecting_audio_checks_first_track_only(self):
        info = MediaInfo(duration=5.0, audio_tracks=("aac", "aac"))
        with (
            patch("denoise_cli.gui.resolve_ffmpeg", return_value="ffmpeg"),
            patch("denoise_cli.gui.probe_media", return_value=info),
        ):
            self.app.set_input(Path("lagu.m4a"))
            self.wait_for(lambda: len(self.app.track_vars) == 2)

        self.assertEqual(self.app.selected_tracks(), [1])

    def test_unsupported_file_shows_error(self):
        self.app.set_input(Path("dokumen.txt"))
        self.assertIn("belum didukung", self.app.status_var.get())

    def test_process_runs_in_background_and_reports_done(self):
        info = MediaInfo(duration=1.0, audio_tracks=("pcm_s16le",))

        def fake_process(**kwargs):
            kwargs["on_progress"](0.5)
            kwargs["on_progress"](1.0)
            return []

        with TemporaryDirectory() as directory:
            source = Path(directory) / "rekaman.wav"
            source.write_bytes(b"audio")
            with (
                patch("denoise_cli.gui.resolve_ffmpeg", return_value="ffmpeg"),
                patch("denoise_cli.gui.probe_media", return_value=info),
                patch("denoise_cli.gui.process_media", side_effect=fake_process) as process,
            ):
                self.app.set_input(source)
                self.wait_for(lambda: len(self.app.track_vars) == 1)
                self.app.preset_var.set(PRESET_LABELS["strong"])
                self.app._start()
                self.wait_for(lambda: self.app.status_var.get().startswith("Selesai"))

        kwargs = process.call_args.kwargs
        self.assertEqual(kwargs["preset_name"], "strong")
        self.assertEqual(kwargs["tracks"], [1])
        self.assertEqual(kwargs["engine"], "deepfilter")
        self.assertEqual(self.app.progress["value"], 100)
        self.assertEqual(str(self.app.run_button["state"]), "normal")


if __name__ == "__main__":
    unittest.main()
