#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "The app is not installed yet. Run the installer first:"
  echo "  ./install-mac.sh"
  exit 1
fi
exec .venv/bin/python tools/serve.py
