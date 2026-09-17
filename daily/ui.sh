#!/bin/bash
# Starts the Pinloop Jobs web app and opens it in the browser.
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if curl -s -o /dev/null http://127.0.0.1:5177/api/run/status; then open http://127.0.0.1:5177; exit 0; fi
exec .venv/bin/python app.py
