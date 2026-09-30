# Progress Proyek Local Denoise CLI

Pembaruan terakhir: 30 September 2026

## Status

Versi `0.3.0` selesai dan dapat dijalankan secara lokal melalui command CLI
maupun executable Windows mandiri. Project menggunakan Python dan binary FFmpeg
dari paket `imageio-ffmpeg`, sehingga media tidak dikirim ke server atau layanan
eksternal.

## Yang Sudah Selesai

- CLI `denoise` untuk memproses file audio dan track audio pada video.
- Engine AI `deepfilter` (default) memakai binary resmi DeepFilterNet 0.5.6
  (MIT/Apache-2.0, modul `denoise_cli.deepfilter`). Pipeline: FFmpeg ekstrak
  track terpilih ke WAV 48 kHz, lalu `deep-filter --compensate-delay`, lalu
  FFmpeg menggabungkan kembali (video disalin, track lain disalin, metadata track
  dipertahankan). Binary diunduh sekali ke `%LOCALAPPDATA%\local-denoise`
  dengan verifikasi SHA-256 (Windows, Linux x86_64, macOS arm64/x86_64), atau
  dibaca dari `DENOISE_DEEPFILTER`, atau dari bundel PyInstaller. Preset:
  `light` = `--atten-lim-db 20`, `balanced` = redaman penuh, `strong` = `--pf`.
  Progres tahap AI diperkirakan dari durasi karena binary tidak melaporkannya.
- Alasan engine default diganti: pada rekaman uji dengan noise keras dan tidak
  stabil (keyboard/keramaian), `spectral` hanya mengubah level noise di jeda
  sebesar -0.7 dB, RNNoise 7 dB, dan DeepFilterNet 22 dB (31 dB dengan `strong`).
- Engine `spectral` (FFmpeg `afftdn`) dengan preset `light`, `balanced`, dan
  `strong`, serta pengaturan manual melalui `--reduction` dan `--noise-floor`.
- Engine neural `rnnoise` (FFmpeg `arnndn`) melalui `--engine rnnoise` dengan
  file model `.rnnn` dari `--model` atau `DENOISE_RNNOISE_MODEL`. Path model
  di-escape agar aman untuk spasi, titik dua, koma, kurung siku, dan tanda kutip.
- Dukungan beberapa track audio: default semua track video diproses, `--track N`
  (dapat diulang) memilih track tertentu dan track lain disalin tanpa diubah.
  `--list-tracks` menampilkan daftar track audio.
- Probing input sebelum proses: file rusak/bukan media, video tanpa audio, dan
  nomor track yang tidak ada menghasilkan pesan error yang jelas.
- Indikator progres satu baris (persentase dari durasi media) saat stderr adalah
  terminal; dapat dimatikan dengan `--quiet`. Ctrl+C menghentikan FFmpeg,
  membersihkan file sementara, dan keluar dengan kode 130.
- Nama output otomatis dengan pola `<nama>.denoised.<ekstensi>`.
- Opsi `--output`, `--force`, `--ffmpeg`, `--dry-run`, dan `--version`.
- Pemrosesan atomik melalui file sementara.
- Stream video disalin tanpa encode ulang; codec audio dipilih sesuai container
  output (MP3 untuk AVI, MP2 untuk MPEG/MPG, OPUS untuk WEBM, AAC untuk MP4/MOV).
- Tampilan desktop Tkinter (`denoise-gui`, modul `denoise_cli.gui`): pilih
  input/output lewat dialog, pilih engine/preset/model, centang track audio,
  progress bar dengan status tiap tahap, tombol Batal, dan Buka folder hasil. Proses berjalan di thread
  terpisah sehingga jendela tetap responsif; FFmpeg dijalankan tanpa jendela
  konsol.
- Skrip `scripts\build-exe.ps1` untuk membuat `dist\denoise.exe` (CLI) dan
  `dist\denoise-gui.exe` (GUI) dengan PyInstaller, one-file; FFmpeg dan binary
  DeepFilterNet ikut dibundel sehingga executable berjalan tanpa internet.
- Dokumentasi cara menjalankan dalam `README.md`.
- Workflow GitHub Actions untuk pengujian di Windows dan Linux.

## Format yang Didukung

Audio: WAV, FLAC, MP3, M4A, AAC, OGG, OGA, OPUS, dan WMA.

Video: MP4, MOV, M4V, MKV, WEBM, AVI, MPEG, MPG, TS, MTS, dan M2TS.

## Validasi Terakhir

- 50 unit test lulus (tes GUI otomatis dilewati bila Tk/display tidak tersedia).
- Engine deepfilter diuji dengan binary asli: unduhan pertama ke cache kosong,
  video MP4 satu track, MKV dua track, dry-run tanpa unduhan, GUI, dan
  `dist\denoise.exe` dengan cache kosong (memakai binary bundel, tanpa unduh).
- GUI diuji dengan FFmpeg asli: proses track tertentu pada MKV, RNNoise, batal
  di tengah file 10 menit (file sementara terhapus), dan video tanpa audio.
- Uji end-to-end dengan FFmpeg 7.1: WAV, MP4, MKV dua track (semua track dan
  `--track 2`), `--list-tracks`, engine rnnoise dengan path model berisi karakter
  khusus, video tanpa audio, file bukan media, dan nomor track tidak valid.
- Progres terverifikasi pada file FLAC 10 menit.
- `dist\denoise.exe` hasil build berhasil memproses MKV dan WAV (rnnoise) tanpa
  virtual environment aktif.

## Catatan Lingkungan

- Folder proyek pernah dipindah dari `Desktop\denoise` ke
  `Desktop\Portfolio\denoise`. `.venv` telah diperbaiki (instalasi editable dan
  skrip aktivasi menunjuk ke lokasi baru). Jika proyek dipindah lagi, buat ulang
  `.venv` lalu jalankan `python -m pip install -e .`.

## Batasan Saat Ini

- Engine `spectral` paling efektif untuk noise stabil; noise yang bertumpuk kuat
  dengan ucapan tidak selalu dapat dipisahkan dengan bersih.
- Engine `rnnoise` dioptimalkan untuk ucapan dan dapat menghilangkan musik atau
  suara non-ucapan. Output rnnoise di-resample ke 48 kHz.
- Model RNNoise tidak dibundel; pengguna perlu mengunduh file `.rnnn` sendiri.
- Engine `deepfilter` membuang semua suara non-ucapan termasuk musik latar;
  gunakan `spectral` untuk musik. Pemakaian pertama (non-exe) butuh internet
  untuk mengunduh binary sekitar 27 MB. File WAV sementara dibuat di folder temp
  sistem (sekitar 11 MB per menit per track).

## Pengembangan Berikutnya

- Progres asli untuk tahap AI (misalnya memproses audio per potongan).
- Pemrosesan batch untuk banyak file atau satu folder sekaligus.
