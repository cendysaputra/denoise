# Local Denoise CLI

CLI ringan untuk mengurangi noise pada audio atau track suara di dalam video.
Semua pemrosesan berjalan di komputer lokal. Video disalin tanpa encode ulang;
hanya audionya yang diproses.

Tersedia dua engine:

- `spectral` (default): spectral denoise FFmpeg (`afftdn`). Cepat, tanpa model,
  cocok untuk noise stabil seperti kipas, AC, hum, dan hiss.
- `rnnoise`: neural network RNNoise (`arnndn`) yang dioptimalkan untuk ucapan.
  Membutuhkan file model `.rnnn`.

## Cara Menjalankan

Butuh Python 3.10 atau lebih baru. Dari folder proyek (PowerShell):

```powershell
# 1. Sekali saja: buat virtual environment dan pasang program
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .

# 2. Jalankan
denoise rekaman.wav
```

Hasilnya tersimpan sebagai `rekaman.denoised.wav` di folder yang sama. Pada sesi
terminal berikutnya cukup aktifkan lagi environment-nya dengan
`.venv\Scripts\Activate.ps1`, lalu jalankan `denoise`.

## Tampilan Desktop (UI)

Jika lebih suka tanpa mengetik perintah, buka tampilan desktop:

```powershell
denoise-gui
```

Tanpa aktivasi environment, jalankan `.venv\Scripts\denoise-gui.exe` atau
`dist\denoise-gui.exe` (lihat bagian Executable Windows). File tersebut juga
bisa dibuka dengan klik dua kali.

Langkah pemakaian:

1. Klik **Pilih...** di baris *File input*, lalu pilih audio atau video dari
   folder mana saja.
2. Lokasi hasil terisi otomatis (`<nama>.denoised.<ekstensi>` di folder yang
   sama). Klik **Ubah...** untuk menyimpan di tempat lain.
3. Pilih metode dan kekuatan. Untuk RNNoise, pilih juga file model `.rnnn`.
4. Centang track audio yang ingin dibersihkan.
5. Klik **Proses**. Progres tampil di bar; **Batal** menghentikan proses, dan
   **Buka folder hasil** muncul setelah selesai.

Jika PowerShell menolak menjalankan `Activate.ps1`, jalankan sekali
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, atau panggil program
langsung tanpa aktivasi: `.venv\Scripts\denoise.exe rekaman.wav`.

Paket instalasi sudah menyertakan binary FFmpeg, sehingga setelah instalasi
pemrosesan tidak membutuhkan koneksi internet.

## Contoh Pemakaian

```powershell
# Tentukan output dan gunakan pengurangan noise yang lebih kuat
denoise wawancara.mp4 -o wawancara-bersih.mp4 --preset strong

# Pemrosesan ringan agar detail musik lebih terjaga
denoise musik.flac --preset light

# Atur parameter secara manual
denoise input.wav --reduction 18 --noise-floor -48

# Engine neural RNNoise untuk rekaman ucapan
denoise podcast.mp3 --engine rnnoise --model models\sh.rnnn

# Lihat track audio di video, lalu proses hanya track 2
denoise film.mkv --list-tracks
denoise film.mkv --track 2

# Timpa output yang sudah ada / lihat command FFmpeg tanpa memproses
denoise rekaman.mp3 --force
denoise rekaman.mp3 --dry-run
```

Gunakan `denoise --help` untuk melihat semua opsi.

### Preset (engine spectral)

- `light`: ringan, cocok untuk musik atau rekaman yang detailnya perlu dijaga.
- `balanced`: default untuk ucapan dan pemakaian umum.
- `strong`: lebih agresif; dapat membuat suara terdengar tipis atau metalik.

### Model RNNoise

Engine `rnnoise` membutuhkan file model `.rnnn`, misalnya dari repositori
[rnnoise-models](https://github.com/GregorR/rnnoise-models). Untuk rekaman
ucapan, model `somnolent-hogwash` (`sh.rnnn`) adalah pilihan awal yang baik.
Lokasi model dapat diberikan lewat `--model` atau environment variable
`DENOISE_RNNOISE_MODEL`. Engine ini bekerja paling baik untuk suara orang
berbicara; untuk musik gunakan engine `spectral`.

### Track audio pada video

Secara default semua track audio pada video diproses. Gunakan `--track N`
(nomor mulai dari 1, dapat diulang) untuk memilih track tertentu; track yang
tidak dipilih tetap disertakan tanpa diubah. Untuk file audio, yang diproses
adalah track pertama atau satu track yang dipilih.

### Format

Audio: WAV, FLAC, MP3, M4A, AAC, OGG, OGA, OPUS, dan WMA. Video: MP4, MOV, M4V,
MKV, WEBM, AVI, MPEG, MPG, TS, MTS, dan M2TS.

Untuk video, ekstensi output harus sama dengan input karena stream video disalin
tanpa encode ulang. Jika ingin memakai FFmpeg sendiri, berikan lokasinya melalui
`--ffmpeg` atau environment variable `DENOISE_FFMPEG`.

## Executable Windows

Untuk membuat executable yang dapat dipakai di komputer tanpa Python:

```powershell
.\scripts\build-exe.ps1
```

Hasilnya ada di folder `dist`:

- `denoise-gui.exe`: tampilan desktop, cukup klik dua kali.
- `denoise.exe`: versi command line, misalnya `dist\denoise.exe rekaman.wav`.

Keduanya sudah membawa FFmpeg sendiri dan dapat disalin ke folder mana saja.

## Menjalankan Tes

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```
