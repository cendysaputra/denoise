# Progress Proyek Local Denoise CLI

Pembaruan terakhir: 30 September 2026

## Status

Versi `0.2.0` selesai dan dapat dijalankan secara lokal melalui command CLI
maupun executable Windows mandiri. Project menggunakan Python dan binary FFmpeg
dari paket `imageio-ffmpeg`, sehingga media tidak dikirim ke server atau layanan
eksternal.

## Yang Sudah Selesai

- CLI `denoise` untuk memproses file audio dan track audio pada video.
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
- Skrip `scripts\build-exe.ps1` untuk membuat `dist\denoise.exe` (PyInstaller,
  one-file, FFmpeg ikut dibundel).
- Dokumentasi cara menjalankan dalam `README.md`.
- Workflow GitHub Actions untuk pengujian di Windows dan Linux.

## Format yang Didukung

Audio: WAV, FLAC, MP3, M4A, AAC, OGG, OGA, OPUS, dan WMA.

Video: MP4, MOV, M4V, MKV, WEBM, AVI, MPEG, MPG, TS, MTS, dan M2TS.

## Validasi Terakhir

- 30 unit test lulus.
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

## Pengembangan Berikutnya

- Engine DeepFilterNet untuk kualitas ucapan yang lebih tinggi (butuh dependensi
  PyTorch/ONNX yang besar).
- Pemrosesan batch untuk banyak file atau satu folder sekaligus.
