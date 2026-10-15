#!/bin/sh
# Release assets in dist/: nreality.apworld and the NReality.yaml options template.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/.local/release.log"
run() { "$@" > "$LOG" 2>&1 || { tail -20 "$LOG"; exit 1; }; }

mkdir -p "$ROOT/dist"
run sh "$ROOT/tools/mwgg.sh" Launcher.py "Build APWorlds" -- --skip_open_folder NReality
cp "$ROOT/.local/vendor/MultiworldGG/build/apworlds/nreality.apworld" "$ROOT/dist/"
rm -rf "$ROOT/.local/templates"
run sh "$ROOT/tools/mwgg.sh" -c 'import sys; from Options import generate_yaml_templates; generate_yaml_templates(sys.argv[1])' "$ROOT/.local/templates"
cp "$ROOT/.local/templates/NReality.yaml" "$ROOT/dist/"
ls -l "$ROOT/dist"
