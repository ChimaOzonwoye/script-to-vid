# Installs script to vid on Windows.
#
#   irm https://raw.githubusercontent.com/ChimaOzonwoye/script-to-vid/main/install.ps1 | iex
#
# Run from inside a copy of the repository it installs that copy in place.
# Run on its own it downloads the repository first.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # the progress bar makes downloads crawl

$Repo = "https://github.com/ChimaOzonwoye/script-to-vid"
$Zip = "$Repo/archive/refs/heads/main.zip"
$Dest = if ($env:STV_DIR) { $env:STV_DIR } else { Join-Path $HOME "script-to-vid" }

function Fail($msg) {
    Write-Host ""
    Write-Host $msg
    Write-Host ""
    exit 1
}

Write-Host "Installing script to vid."
Write-Host ""

# ---- Python -----------------------------------------------------------
$Py = $null
foreach ($c in @("py", "python", "python3")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) {
        & $c -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Py = $c; break }
    }
}
if (-not $Py) {
    Fail ("This needs Python 3.10 or newer, and I could not find it.`n" +
          "Install it from https://www.python.org/downloads/ and tick`n" +
          "'Add python.exe to PATH' on the first screen, then paste this`n" +
          "command again.")
}
Write-Host "Using $(& $Py --version)."

# ---- the code ---------------------------------------------------------
if ((Test-Path "requirements.txt") -and (Test-Path "app")) {
    $Dest = (Get-Location).Path
    Write-Host "Installing into this folder."
} else {
    Write-Host "Downloading into $Dest."
    $tmp = Join-Path $env:TEMP "script-to-vid.zip"
    try {
        Invoke-WebRequest $Zip -OutFile $tmp
    } catch {
        Fail ("The download failed. Check your internet connection and paste`n" +
              "the command again.")
    }
    $stage = Join-Path $env:TEMP "script-to-vid-stage"
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
    Expand-Archive $tmp -DestinationPath $stage -Force
    $inner = Get-ChildItem $stage -Directory | Select-Object -First 1
    if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
    Move-Item $inner.FullName $Dest
    Remove-Item $tmp -Force
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}
Set-Location $Dest

# ---- dependencies -----------------------------------------------------
Write-Host "Setting up. This takes a few minutes the first time."
& $Py -m venv .venv
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Fail ("Could not create the Python environment. Reinstall Python from`n" +
          "https://www.python.org/downloads/ and paste the command again.")
}
& .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Fail ("The Python packages could not be downloaded. Check your internet`n" +
          "connection and paste the command again.")
}

# ---- ffmpeg -----------------------------------------------------------
$haveFfmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
              (Test-Path "ffmpeg\bin\ffmpeg.exe")
if (-not $haveFfmpeg) {
    Write-Host "Downloading ffmpeg, the video engine. About 80 MB, one time only."
    $zip = Join-Path $env:TEMP "ffmpeg.zip"
    try {
        Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip
    } catch {
        Fail ("ffmpeg could not be downloaded. Check your internet connection`n" +
              "and paste the command again.")
    }
    $stage = Join-Path $env:TEMP "ffmpeg-stage"
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
    Expand-Archive $zip -DestinationPath $stage -Force
    $inner = Get-ChildItem $stage -Directory | Select-Object -First 1
    if (Test-Path "ffmpeg") { Remove-Item "ffmpeg" -Recurse -Force }
    Move-Item $inner.FullName "ffmpeg"
    Remove-Item $zip -Force
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}

# ---- voice samples ----------------------------------------------------
# only the previews in the voice picker; a failure here is not a failed install
Write-Host "Preparing voice samples."
$env:PATH = "$Dest\ffmpeg\bin;$env:PATH"
& .venv\Scripts\python.exe tools\generate_voices.py 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "  (samples skipped, the voices still work)" }

# ---- shortcut and launch ---------------------------------------------
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) "script to vid.lnk"))
$lnk.TargetPath = Join-Path $Dest "run.bat"
$lnk.WorkingDirectory = $Dest
$lnk.Save()

Write-Host ""
Write-Host "Done. Opening it now."
Write-Host "Next time, use the 'script to vid' shortcut on your Desktop."
Write-Host ""
& (Join-Path $Dest "run.bat")
