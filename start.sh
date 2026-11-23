#!/usr/bin/env sh
# Starts AI Mod Painter on macOS / Linux: ./start.sh [ROOT_FOLDER]
# The first start prepares the Python environment with uv (https://docs.astral.sh/uv/).
set -e
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv was not found. Install it from https://docs.astral.sh/uv/ and run ./start.sh again." >&2
    exit 20
fi

if ! uv sync --locked --quiet; then
    echo "Preparing the Python environment failed, see the messages above." >&2
    exit 21
fi

# .venv/bin on macOS / Linux, .venv/Scripts in Git Bash on Windows.
if [ -x .venv/bin/ai-mod-painter ]; then
    exec .venv/bin/ai-mod-painter "$@"
fi
exec .venv/Scripts/ai-mod-painter.exe "$@"
