# Third-Party Notices

Local Denoise memakai komponen pihak ketiga berikut. Tidak ada kode sumber
komponen ini yang disalin ke repositori; komponen dipasang sebagai dependensi,
diunduh saat dipakai, atau dibundel ke dalam executable di `dist\`.

| Komponen | Versi | Lisensi | Cara dipakai |
|---|---|---|---|
| [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) (`deep-filter`) | 0.5.6 | MIT atau Apache-2.0 | Diunduh saat pertama dipakai; dibundel di executable |
| [FFmpeg](https://ffmpeg.org) (build [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) "essentials") | 7.1 | GPL-3.0-or-later | Disediakan `imageio-ffmpeg`; dibundel di executable |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | 0.6.0 | BSD-2-Clause | Dependensi Python; dibundel di executable |
| [Python](https://www.python.org) | 3.13 | PSF-2.0 | Runtime yang dibundel di executable |
| [Tcl/Tk](https://www.tcl-lang.org) | 8.6 | Tcl/Tk License (BSD-style) | Tampilan desktop, dibundel di `denoise-gui.exe` |
| [PyInstaller](https://pyinstaller.org) bootloader | 6.x | GPL-2.0-or-later dengan bootloader exception | Pembuat executable |

Model RNNoise (`.rnnn`) tidak disertakan; pengguna mengunduhnya sendiri.

## Catatan untuk distribusi executable

- **FFmpeg (GPL-3.0).** Binary FFmpeg dibuat dengan `--enable-gpl
  --enable-version3`. Jika `denoise.exe` atau `denoise-gui.exe` dibagikan ke
  orang lain, kode sumber FFmpeg yang sesuai juga harus tersedia bagi penerima,
  misalnya dengan melampirkan
  [ffmpeg-7.1.tar.xz](https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz) beserta
  informasi build dari [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) pada
  rilis yang sama. Local Denoise menjalankan FFmpeg sebagai program terpisah,
  tidak di-link ke kode Local Denoise.
- **DeepFilterNet.** Binary `deep-filter` juga memuat library Rust pihak ketiga
  yang masing-masing memiliki lisensinya sendiri, umumnya MIT atau Apache-2.0.
- **PyInstaller.** Bootloader exception mengizinkan executable hasil build
  didistribusikan dengan lisensi apa pun.

---

## DeepFilterNet — MIT License

Dilisensikan ganda MIT atau Apache-2.0; di sini dipilih MIT. Teks Apache-2.0:
https://www.apache.org/licenses/LICENSE-2.0

```
The MIT License (MIT)
Copyright (c) 2021 Hendrik Schröter

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## imageio-ffmpeg — BSD 2-Clause License

```
BSD 2-Clause License

Copyright (c) 2019-2025, imageio
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## Lisensi lainnya

- FFmpeg: https://ffmpeg.org/legal.html — GPL-3.0: https://www.gnu.org/licenses/gpl-3.0.html
- Python: https://docs.python.org/3/license.html
- Tcl/Tk: https://www.tcl-lang.org/software/tcltk/license.html
- PyInstaller: https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt
