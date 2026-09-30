# Local Denoise

Menghapus noise dari audio atau video secara lokal di komputer sendiri.
Menggunakan AI [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet), dan
gambar video disalin tanpa encode ulang.

## Instalasi

Butuh Python 3.10+. Dari folder proyek (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Engine AI (sekitar 27 MB) diunduh otomatis saat pertama dipakai. Setelah itu
program berjalan offline.

## Pemakaian

**Tampilan desktop:** jalankan `denoise-gui`, pilih file, lalu klik **Proses**.

**Command line:**

```powershell
denoise video.mp4                    # hasil: video.denoised.mp4
denoise video.mp4 --preset strong    # buang noise lebih banyak
denoise lagu.mp3 --engine spectral   # untuk musik
denoise --help                       # semua opsi
```

- Preset: `light`, `balanced` (default), `strong`.
- Engine: `deepfilter` (default, untuk suara orang), `spectral` (untuk musik
  atau desis stabil), `rnnoise` (butuh file model `.rnnn`).

## Executable Windows

```powershell
.\scripts\build-exe.ps1
```

Hasilnya `dist\denoise-gui.exe` dan `dist\denoise.exe`, yang bisa dipakai
tanpa Python maupun internet. Jika executable dibagikan, sertakan
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) (ikut tersalin ke `dist\`).

## Tes

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests
```
