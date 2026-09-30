# Local Denoise CLI

CLI ringan untuk mengurangi noise pada audio atau track suara di dalam video.
Semua pemrosesan berjalan di komputer lokal. Video disalin tanpa encode ulang;
hanya audionya yang diproses.

Tersedia tiga engine:

- `deepfilter` (default): AI [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet)
  untuk suara orang. Membersihkan noise keras dan tidak stabil seperti ketikan
  keyboard, keramaian, atau lalu lintas. Binary-nya (sekitar 27 MB) diunduh
  otomatis sekali saat pertama dipakai, diverifikasi dengan SHA-256, lalu
  disimpan di `%LOCALAPPDATA%\local-denoise`. Setelah itu berjalan offline.
- `rnnoise`: neural network RNNoise (`arnndn`) yang lebih ringan. Membutuhkan
  file model `.rnnn`.
- `spectral`: spectral denoise FFmpeg (`afftdn`). Hanya efektif untuk desis
  stabil seperti kipas, AC, atau hum; cocok untuk musik karena tidak membuang
  suara non-ucapan.

Engine AI membuang semua suara yang bukan ucapan, termasuk musik latar. Untuk
rekaman musik gunakan `--engine spectral`.

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
3. Pilih metode dan kekuatan. Default *AI DeepFilterNet - Seimbang* sudah cocok
   untuk rekaman suara. Untuk RNNoise, pilih juga file model `.rnnn`.
4. Centang track audio yang ingin dibersihkan.
5. Klik **Proses**. Progres tampil di bar; **Batal** menghentikan proses, dan
   **Buka folder hasil** muncul setelah selesai.

Jika PowerShell menolak menjalankan `Activate.ps1`, jalankan sekali
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, atau panggil program
langsung tanpa aktivasi: `.venv\Scripts\denoise.exe rekaman.wav`.

Paket instalasi sudah menyertakan binary FFmpeg. Koneksi internet hanya
dibutuhkan sekali, saat engine AI dipakai pertama kali.

## Contoh Pemakaian

```powershell
# Tentukan output dan buang noise semaksimal mungkin
denoise wawancara.mp4 -o wawancara-bersih.mp4 --preset strong

# Sisakan sedikit suasana ruangan agar suara tidak terlalu "kering"
denoise vlog.mp4 --preset light

# Rekaman musik: pakai spectral agar musiknya tidak ikut dibuang
denoise musik.flac --engine spectral --preset light
denoise input.wav --engine spectral --reduction 18 --noise-floor -48

# Engine neural RNNoise untuk rekaman ucapan
denoise podcast.mp3 --engine rnnoise --model models\sh.rnnn

# Lihat track audio di video, lalu proses hanya track 2
denoise film.mkv --list-tracks
denoise film.mkv --track 2

# Timpa output yang sudah ada / lihat command tanpa memproses
denoise rekaman.mp3 --force
denoise rekaman.mp3 --dry-run
```

Gunakan `denoise --help` untuk melihat semua opsi.

### Preset

| Preset | `deepfilter` | `spectral` |
|---|---|---|
| `light` | redaman dibatasi 20 dB, sisa suasana ruangan masih terdengar | ringan, detail musik terjaga |
| `balanced` (default) | redaman penuh | untuk pemakaian umum |
| `strong` | redaman penuh + post-filter, paling bersih | agresif, suara bisa terdengar metalik |

Pada contoh rekaman berisik (keyboard dan keramaian), engine `deepfilter`
menurunkan noise di jeda bicara sekitar 22 dB dengan preset `balanced` dan 31 dB
dengan `strong`. Engine `spectral` praktis tidak berpengaruh pada noise seperti
itu.

Jika ingin memakai binary DeepFilterNet sendiri, set environment variable
`DENOISE_DEEPFILTER` ke lokasi file `deep-filter`.

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

Keduanya sudah membawa FFmpeg dan engine AI DeepFilterNet sendiri, sehingga
bisa langsung dipakai tanpa internet dan dapat disalin ke folder mana saja.

## Menjalankan Tes

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```
