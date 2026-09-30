# Membuat dist\denoise.exe (CLI) dan dist\denoise-gui.exe (tampilan desktop)
# yang dapat dijalankan tanpa instalasi Python.
# Jalankan dari folder proyek: .\scripts\build-exe.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Membuat virtual environment .venv ..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Gagal membuat virtual environment." }
}

& $python -m pip install --quiet -e ".[build]"
if ($LASTEXITCODE -ne 0) { throw "Gagal memasang dependensi build." }

# Bundel engine AI DeepFilterNet agar executable dapat dipakai tanpa internet.
# Binary diunduh ke cache (dengan verifikasi SHA-256) bila belum ada.
$deepFilter = & $python -c "from denoise_cli import deepfilter; print(deepfilter.resolve_binary())"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $deepFilter)) {
    throw "Gagal menyiapkan binary DeepFilterNet."
}
$deepFilterArg = "$deepFilter;deepfilter"

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name denoise `
    --paths src `
    --collect-binaries imageio_ffmpeg `
    --add-binary $deepFilterArg `
    --specpath build `
    src\denoise_cli\__main__.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller gagal membuat executable." }

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name denoise-gui `
    --paths src `
    --collect-binaries imageio_ffmpeg `
    --add-binary $deepFilterArg `
    --specpath build `
    src\denoise_cli\gui.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller gagal membuat executable GUI." }

& (Join-Path $root "dist\denoise.exe") --version
if ($LASTEXITCODE -ne 0) { throw "Executable hasil build gagal dijalankan." }
Write-Host "Selesai:"
Write-Host "  CLI: $(Join-Path $root 'dist\denoise.exe')"
Write-Host "  GUI: $(Join-Path $root 'dist\denoise-gui.exe')"
