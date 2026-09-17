#!/bin/bash
# The one daily command. Usage: daily/run.sh [--no-pull] [--from "job boards"]
set -e
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
mkdir -p logs
exec .venv/bin/python daily.py "$@" 2>&1 | tee -a "logs/$(date +%F).log"
