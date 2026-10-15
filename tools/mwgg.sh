#!/bin/sh
# Run a MultiworldGG entry point from the development checkout. Use absolute paths for files, e.g.
#   sh tools/mwgg.sh Launcher.py "NReality Client"
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/.local/vendor/MultiworldGG"
exec "$ROOT/.local/venv-mwgg/bin/python" "$@"
