#!/bin/bash
# full rebuild of Korean patch from original CIA (run from anywhere)
set -e
W="$(cd "$(dirname "$0")/.." && pwd)"; cd "$W"
O=".."
if [ ! -f dec/bin/lh1.0.ncch ]; then
  mkdir -p dec; cp -r "${DECRYPTOR_BIN:?set DECRYPTOR_BIN to Batch-CIA-3DS-Decryptor-Redux bin folder}" dec/bin
  cp "$O/Lost Heroes (Bonus Edition) (Japan) (eShop).cia" dec/lh1.cia
  (cd dec && echo | bin/decrypt.exe lh1.cia >/dev/null 2>&1; rm -f lh1.cia)
fi
if [ ! -d ext/romfs ]; then
python -I - <<'EOF'
import sys;sys.path.insert(0,'tools')
from ctr import *
f=open('dec/bin/lh1.0.ncch','rb');i=ncch_info(f,0)
exefs_extract(f,i['exefs'][0],'ext/exefs');romfs_extract(f,i['romfs'][0],'ext/romfs')
EOF
fi
rm -rf build; mkdir -p build
python -I tools/merge.py
python -I tools/kbuild.py; grep -E "glyphs|fails|packs" build_log.txt
python -I tools/texbuild.py
python -I tools/staffbuild.py
# movie
python -I - <<'EOF'
import sys,struct;sys.path.insert(0,'tools')
from moflex import parse,frames
b=open('ext/romfs/Movie/opening.moflex','rb').read()
v=[d for s,e,d in frames(parse(b)) if s==0]
with open('mv.pkts','wb') as f:
    f.write(struct.pack('<i',len(v)))
    for d in v: f.write(struct.pack('<i',len(d)));f.write(d)
EOF
rm -rf yuv tgt; ./mobi/bin/mobi.exe decode mv.pkts 400 240 yuv 2918 3069
python -I tools/movlogo.py 2918 3069
MOBI_NOBUDGET=1 ./mobi/bin/mobi.exe transcode mv.pkts 400 240 tgt 2918 3069 tc.pkts > tc.log 2>&1
python -I - <<'EOF'
import sys,os;sys.path.insert(0,'tools')
from moflex import parse
from mux import groups,mux
from apply import readtc
rep=readtc('tc.pkts');b=open('ext/romfs/Movie/opening.moflex','rb').read();gs=groups(parse(b));vi=0
for g in gs:
    for f in g['frames']:
        if f[0]==0:
            if vi in rep: f[2]=rep[vi]
            vi+=1
m,sp=mux(gs);os.makedirs('build/romfs/Movie',exist_ok=True);open('build/romfs/Movie/opening.moflex','wb').write(m);print('movie',len(rep))
EOF
rm -rf yuv tgt mv.pkts tc.pkts
python -I tools/mkncch.py dec/bin/lh1.0.ncch build/romfs build/lh1_ko.ncch
echo BUILD_OK
