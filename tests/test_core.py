import unittest
from pathlib import Path

from denoise_cli.core import (
    DenoiseError,
    build_ffmpeg_command,
    default_output_path,
    denoise_filter,
    media_kind,
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


if __name__ == "__main__":
    unittest.main()
