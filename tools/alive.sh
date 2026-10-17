#!/bin/bash
# usage: alive.sh rom -> prints seconds survived (max 60)
cd "$(dirname "$0")/.."
taskkill //F //IM azahar_lh1.exe >/dev/null 2>&1; sleep 1
python -I tools/launch.py "$1" >/dev/null 2>&1
for i in $(seq 1 24); do sleep 5; [ $(tasklist | grep -ci azahar_lh1) -eq 0 ] && { echo died $((i*5)); exit; }; done
echo alive; taskkill //F //IM azahar_lh1.exe >/dev/null 2>&1
