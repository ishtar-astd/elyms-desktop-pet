#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"

if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
fi

if ! .venv/bin/python -c 'from PyQt5.QtWidgets import QApplication' >/dev/null 2>&1; then
    echo 'Installing the desktop pet dependency for the first launch...'
    .venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
fi

exec .venv/bin/python pet.py
