#!/bin/bash
# FarmBridge quick-start script.
set -e
cd "$(dirname "$0")"

if [ -d "venv" ]; then
  source venv/bin/activate
else
  pip install -r requirements.txt --break-system-packages -q
fi

echo "Starting Farm Bridge..."
python app.py
