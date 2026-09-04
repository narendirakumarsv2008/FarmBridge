#!/bin/bash
# Farm Bridge — development launcher.
#
#   ./run.sh
#
# Activates a local virtualenv if present, installs dependencies and starts
# the Flask development server. See docs/BACKEND_INTEGRATION_GUIDE.md.
set -e
cd "$(dirname "$0")"

if [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

pip install -q -r requirements.txt
python app.py
