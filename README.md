# Local Denoise CLI

CLI ringan untuk mengurangi noise konstan seperti desis kipas, AC, dan hiss pada
audio atau track suara di dalam video. Semua pemrosesan berjalan di komputer
lokal. Video disalin tanpa encode ulang; hanya audionya yang diproses.

Metode yang digunakan adalah spectral denoise dari FFmpeg. Metode ini cepat dan
tidak membutuhkan GPU atau model AI. Hasil terbaik biasanya didapat untuk noise
yang relatif stabil. Suara yang bertumpuk dengan ucapan, seperti musik keras atau
orang lain berbicara, tidak dapat dipisahkan dengan sempurna oleh metode ini.

## Instalasi

Pastikan Python 3.10 atau lebih baru tersedia, lalu jalankan dari folder proyek:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Paket instalasi menyertakan dependensi yang menyediakan binary FFmpeg. Setelah
instalasi selesai, pemrosesan tidak membutuhkan koneksi internet.

## Pemakaian

```powershell
# Preset balanced dan nama output otomatis: rekaman.denoised.wav
denoise rekaman.wav

# Tentukan output dan gunakan pengurangan noise yang lebih kuat
denoise wawancara.mp4 -o wawancara-bersih.mp4 --preset strong

# Pemrosesan ringan agar detail musik lebih terjaga
denoise musik.flac --preset light

# Timpa output yang sudah ada
denoise rekaman.mp3 --force
```

Preset yang tersedia:

- `light`: noise reduction ringan, cocok untuk musik atau rekaman yang detailnya
  perlu dijaga.
- `balanced`: pilihan default untuk ucapan dan pemakaian umum.
- `strong`: lebih agresif untuk noise yang jelas; dapat membuat suara terdengar
  lebih tipis atau metalik.

Parameter dapat diatur secara manual bila diperlukan:

```powershell
denoise input.wav --reduction 18 --noise-floor -48
```

Gunakan `denoise --help` untuk melihat semua opsi. Format audio yang didukung:
WAV, FLAC, MP3, M4A, AAC, OGG, OPUS, dan WMA. Format video yang didukung: MP4,
MOV, M4V, MKV, WEBM, AVI, MPEG, MPG, TS, MTS, dan M2TS.

Jika ingin memakai instalasi FFmpeg sendiri, berikan lokasi executable melalui
`--ffmpeg` atau environment variable `DENOISE_FFMPEG`.

Untuk video, gunakan ekstensi output yang sama dengan input. Program menyalin
stream video tanpa encode ulang agar proses tetap cepat dan kualitas gambar tidak
berubah; konversi container atau codec video belum didukung.

## Menjalankan tes

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```
