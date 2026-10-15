#!/bin/sh
# Development environment: MultiworldGG from source (pinned) with this world linked into worlds/.
set -eu
cd "$(dirname "$0")/.."
COMMIT=c3a271b329e39e795a97927b7c155dc27511b101
PYTHON=${PYTHON:-python3.13}  # MultiworldGG supports Python 3.12-3.13
MW=.local/vendor/MultiworldGG
if [ ! -d "$MW/.git" ]; then
  git init -q "$MW"
  git -C "$MW" remote add origin https://github.com/MultiworldGG/MultiworldGG.git
fi
git -C "$MW" fetch -q --depth 1 origin "$COMMIT"
git -C "$MW" checkout -q FETCH_HEAD
[ -x .local/venv-mwgg/bin/python ] || "$PYTHON" -m venv .local/venv-mwgg
.local/venv-mwgg/bin/pip install -q -r "$MW/requirements.txt" -r "$MW/ci-requirements.txt"
(cd "$MW" && ../../venv-mwgg/bin/python -c "import ModuleUpdate; ModuleUpdate.update(yes=True)")
ln -sfn ../../../../apworld/nreality "$MW/worlds/nreality"
echo "MultiworldGG ready: sh tools/mwgg.sh Launcher.py"
