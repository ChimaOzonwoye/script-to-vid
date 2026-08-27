#!/bin/bash
# Installs script to vid on a Mac. In Terminal:  ./install-mac.sh
cd "$(dirname "$0")"

fail() { echo; echo "$1"; exit 1; }

# --- Python 3.10+ ---
if ! command -v python3 >/dev/null 2>&1 ||
   ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
  fail "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/macos/ and run this installer again."
fi

echo "Setting up (this can take a few minutes the first time)..."

python3 -m venv .venv || fail "The Python environment could not be created. Reinstall Python from https://www.python.org/downloads/macos/ and run this again."
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt ||
  fail "The app's packages could not be downloaded. Check your internet connection and run this installer again."

# --- ffmpeg via Homebrew ---
if ! command -v ffmpeg >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    fail "ffmpeg is needed and Homebrew is not installed. Install Homebrew from https://brew.sh, then run this installer again."
  fi
  echo "Installing ffmpeg with Homebrew (one time only)..."
  brew install ffmpeg || fail "ffmpeg could not be installed. Run 'brew install ffmpeg' yourself, then run this installer again."
fi

# --- desktop shortcut ---
cat > "$HOME/Desktop/script to vid.command" <<EOF
#!/bin/bash
cd "$(pwd)"
./run.sh
EOF
chmod +x "$HOME/Desktop/script to vid.command" run.sh

echo
echo "Done. Double-click 'script to vid' on your Desktop to start."
