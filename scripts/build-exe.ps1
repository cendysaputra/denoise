# Membuat dist\denoise.exe yang dapat dijalankan tanpa instalasi Python.
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

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name denoise `
    --paths src `
    --collect-binaries imageio_ffmpeg `
    --specpath build `
    src\denoise_cli\__main__.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller gagal membuat executable." }

& (Join-Path $root "dist\denoise.exe") --version
if ($LASTEXITCODE -ne 0) { throw "Executable hasil build gagal dijalankan." }
Write-Host "Selesai: $(Join-Path $root 'dist\denoise.exe')"
