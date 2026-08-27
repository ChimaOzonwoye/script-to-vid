# Installs script to vid on Windows.
# Right-click this file and choose "Run with PowerShell".

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

function Fail($msg) {
    Write-Host ""
    Write-Host $msg
    Read-Host "Press Enter to close"
    exit 1
}

# --- Python 3.10+ ---
$python = $null
foreach ($cand in @("py", "python")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        & $cand -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $cand; break }
    }
}
if (-not $python) {
    Fail ("Python 3.10 or newer was not found. Install it from " +
          "https://www.python.org/downloads/ - tick 'Add python.exe to PATH' " +
          "during install - then run this installer again.")
}

Write-Host "Setting up (this can take a few minutes the first time)..."

# --- virtual environment and packages ---
& $python -m venv .venv
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Fail "The Python environment could not be created. Reinstall Python from https://www.python.org/downloads/ and run this again."
}
& .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Fail "The app's packages could not be downloaded. Check your internet connection and run this installer again."
}

# --- ffmpeg ---
$haveFfmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or (Test-Path "ffmpeg\bin\ffmpeg.exe")
if (-not $haveFfmpeg) {
    Write-Host "Downloading ffmpeg (about 80 MB, one time only)..."
    $zip = "$env:TEMP\ffmpeg-release-essentials.zip"
    try {
        Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip
    } catch {
        Fail "ffmpeg could not be downloaded. Check your internet connection and run this installer again."
    }
    Expand-Archive $zip -DestinationPath "$env:TEMP\ffmpeg-extract" -Force
    $inner = Get-ChildItem "$env:TEMP\ffmpeg-extract" -Directory | Select-Object -First 1
    if (Test-Path "ffmpeg") { Remove-Item "ffmpeg" -Recurse -Force }
    Move-Item $inner.FullName "ffmpeg"
    Remove-Item $zip -Force
    Remove-Item "$env:TEMP\ffmpeg-extract" -Recurse -Force -ErrorAction SilentlyContinue
}

# --- desktop shortcut ---
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\script to vid.lnk")
$lnk.TargetPath = "$here\run.bat"
$lnk.WorkingDirectory = $here
$lnk.Save()

Write-Host ""
Write-Host "Done. Use the 'script to vid' shortcut on your Desktop to start."
Read-Host "Press Enter to close"
