#!/bin/sh
# Small startup script that activates the build-time venv and runs the app
set -e

VENVDIR="/app/bot_venv"
APP="/app/app.py"

if [ -x "$VENVDIR/bin/activate" ] || [ -f "$VENVDIR/bin/activate" ]; then
  # Use the venv's python interpreter directly
  exec "$VENVDIR/bin/python" "$APP" "$@"
else
  # Fallback to system python
  exec python "$APP" "$@"
fi
