# Progress Proyek Local Denoise CLI

Pembaruan terakhir: 13 September 2026

## Status

Versi MVP `0.1.0` selesai dan dapat dijalankan secara lokal melalui command CLI.
Project menggunakan Python dan binary FFmpeg dari paket `imageio-ffmpeg`, sehingga
media tidak dikirim ke server atau layanan eksternal.

## Yang Sudah Selesai

- CLI `denoise` untuk memproses file audio dan track audio pada video.
- Preset pengurangan noise `light`, `balanced`, dan `strong`.
- Pengaturan manual melalui `--reduction` dan `--noise-floor`.
- Nama output otomatis dengan pola `<nama>.denoised.<ekstensi>`.
- Opsi `--output`, `--force`, `--ffmpeg`, `--dry-run`, dan `--version`.
- Pemrosesan atomik melalui file sementara agar output yang gagal tidak dianggap
  sebagai hasil akhir.
- Stream video disalin tanpa encode ulang; hanya stream audio yang di-encode.
- Pemilihan codec audio berdasarkan container output, termasuk MP3 untuk AVI,
  MP2 untuk MPEG/MPG, OPUS untuk WEBM, dan AAC untuk MP4/MOV.
- Validasi file input, ekstensi, rentang parameter, output yang sudah ada, dan
  kecocokan jenis media input/output.
- Dokumentasi instalasi dan pemakaian dalam `README.md`.

## Format yang Didukung

Audio: WAV, FLAC, MP3, M4A, AAC, OGG, OGA, OPUS, dan WMA.

Video: MP4, MOV, M4V, MKV, WEBM, AVI, MPEG, MPG, TS, MTS, dan M2TS.

## Validasi Terakhir

- 8 unit test lulus.
- Seluruh modul berhasil melalui pemeriksaan `py_compile`.
- `pip check` melaporkan tidak ada dependensi yang rusak.
- Uji end-to-end WAV berhasil menggunakan FFmpeg 7.1.
- Uji end-to-end MP4 berhasil; stream H.264 disalin dan audio AAC diproses ulang.
- Entry point `.venv\Scripts\denoise.exe` berhasil dijalankan dan melaporkan
  versi `0.1.0`.

## Cara Menjalankan

```powershell
.venv\Scripts\Activate.ps1
denoise rekaman.wav
denoise wawancara.mp4 --preset strong -o wawancara-bersih.mp4
```

Gunakan `denoise --help` untuk melihat seluruh opsi.

## Batasan Saat Ini

- Metode spectral denoise paling efektif untuk noise stabil seperti kipas, AC,
  hum, dan hiss.
- Musik, suara orang lain, atau noise yang bertumpuk kuat dengan ucapan tidak
  selalu dapat dipisahkan dengan bersih.
- Untuk video dengan beberapa track audio, versi saat ini hanya memproses track
  audio pertama.

## Pengembangan Berikutnya

- Menambahkan pilihan engine neural seperti RNNoise atau DeepFilterNet untuk
  kualitas ucapan yang lebih baik.
- Mendukung pemilihan dan pemrosesan beberapa track audio.
- Menambahkan indikator progres yang lebih ringkas untuk video berdurasi panjang.
- Menyediakan paket executable Windows agar dapat digunakan tanpa instalasi
  Python manual.
