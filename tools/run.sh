#!/bin/bash
# usage: run.sh rom shot1-args... ; always kills emulator at end
cd "$(dirname "$0")/.."
taskkill //F //IM azahar_lh1.exe >/dev/null 2>&1; sleep 1
python -I tools/launch.py "$1"; shift
sleep 25
for spec in "$@"; do python -I tools/shot.py $spec; done
taskkill //F //IM azahar_lh1.exe >/dev/null 2>&1
