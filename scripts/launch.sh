#!/usr/bin/env sh
# Starts AI Mod Painter from this repository (needs uv: https://docs.astral.sh/uv/).
set -e
if ! command -v uv >/dev/null 2>&1; then
    echo "uv was not found. Install uv, then run this launcher again." >&2
    exit 20
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec uv run --project "$ROOT" ai-mod-painter "$@"
