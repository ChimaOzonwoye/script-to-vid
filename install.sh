#!/bin/bash
# Installs script to vid on a Mac.
#
#   curl -fsSL https://raw.githubusercontent.com/ChimaOzonwoye/script-to-vid/main/install.sh | bash
#
# Run from inside a copy of the repository it installs that copy in place.
# Run on its own it downloads the repository first.
#
# Nothing here reads from stdin, because stdin is this script when it arrives
# through a pipe and any prompt would swallow the rest of the file.

set -u

REPO="https://github.com/ChimaOzonwoye/script-to-vid"
TARBALL="$REPO/archive/refs/heads/main.tar.gz"
DEST="${STV_DIR:-$HOME/script-to-vid}"

say()  { printf '%s\n' "$1"; }
fail() { printf '\n%s\n' "$1"; exit 1; }

say "Installing script to vid."
say ""

# ---- Python -----------------------------------------------------------
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 &&
     "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || fail "This needs Python 3.10 or newer, and I could not find it.
Install it from https://www.python.org/downloads/macos/ and then run this
command again."
say "Using $($PY --version)."

# ---- the code ---------------------------------------------------------
if [ -f "requirements.txt" ] && [ -d "app" ]; then
  DEST="$(pwd)"
  say "Installing into this folder."
else
  if [ -d "$DEST/.git" ] && command -v git >/dev/null 2>&1; then
    say "Updating the copy already in $DEST."
    git -C "$DEST" pull --quiet --ff-only || say "  (kept the copy you have)"
  elif command -v git >/dev/null 2>&1; then
    say "Downloading into $DEST."
    rm -rf "$DEST"
    git clone --quiet --depth 1 "$REPO" "$DEST" ||
      fail "The download failed. Check your internet connection and run the
command again."
  else
    say "Downloading into $DEST."
    rm -rf "$DEST"; mkdir -p "$DEST"
    curl -fsSL "$TARBALL" | tar -xz -C "$DEST" --strip-components=1 ||
      fail "The download failed. Check your internet connection and run the
command again."
  fi
fi
cd "$DEST" || fail "Could not open $DEST."

# ---- dependencies -----------------------------------------------------
say "Setting up. This takes a few minutes the first time."
"$PY" -m venv .venv 2>/dev/null || fail "Could not create the Python environment.
Reinstall Python from https://www.python.org/downloads/macos/ and try again."
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt ||
  fail "The Python packages could not be downloaded. Check your internet
connection and run the command again."

# ---- ffmpeg -----------------------------------------------------------
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    say "Installing ffmpeg, the video engine."
    brew install ffmpeg >/dev/null 2>&1 ||
      fail "ffmpeg could not be installed. Run 'brew install ffmpeg' yourself,
then run this command again."
  else
    fail "This needs ffmpeg, and Homebrew is not installed to fetch it.
Install Homebrew from https://brew.sh, then run this command again."
  fi
fi

# ---- voice samples ----------------------------------------------------
# only the previews in the voice picker; a failure here is not a failed install
say "Preparing voice samples."
.venv/bin/python tools/generate_voices.py 2>/dev/null ||
  say "  (samples skipped, the voices still work)"

# ---- shortcut and launch ---------------------------------------------
chmod +x run.sh 2>/dev/null
cat > "$HOME/Desktop/script to vid.command" <<EOF 2>/dev/null
#!/bin/bash
cd "$DEST"
./run.sh
EOF
chmod +x "$HOME/Desktop/script to vid.command" 2>/dev/null

say ""
say "Done. Opening it now."
say "Next time, double-click 'script to vid' on your Desktop."
say ""
exec ./run.sh
