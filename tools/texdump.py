# dump all unique CTPK textures (in packs and loose) to texdump/<md5>.png + index json
import glob, os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
from lz11 import comp_dec
from nbf import parse
from ctpk import textures
import texdec as T
B = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(B, 'texdump'); os.makedirs(OUT, exist_ok=True)
idx = {}  # md5 -> {fmt,w,h,refs:[[pack,entry,ti]]}
def handle(pack, entry, d):
    for ti, t in enumerate(textures(d)):
        raw = d[t['pos']:t['pos'] + t['size']]
        h = hashlib.md5(raw).hexdigest()
        r = idx.setdefault(h, dict(fmt=t['fmt'], w=t['w'], h=t['h'], name=t['name'], refs=[]))
        r['refs'].append([pack, entry, ti])
        p = os.path.join(OUT, h + '.png')
        if not os.path.exists(p):
            try:
                img = T.decode(t['fmt'], raw, t['w'], t['h'])
                Image.fromarray(img).save(p)
            except Exception as e:
                r['err'] = str(e)
root = os.path.join(B, 'ext', 'romfs')
for f in sorted(glob.glob(os.path.join(root, '**', '*'), recursive=True)):
    rel = os.path.relpath(f, root).replace(os.sep, '/')
    if not os.path.isfile(f) or rel.endswith(('.bcstm', '.moflex', '.bcsar', '.mbb', '.bla')): continue
    b = open(f, 'rb').read()
    if b[:4] == b'COMP':
        try: b = comp_dec(b)
        except Exception: continue
    if b[:4] == b'2NBF':
        for n, u, d in parse(b)[1]:
            if d[:4] == b'GFPT' or d[:4] == b'CTPK': handle(rel, n, d)
    elif b[:4] in (b'GFPT', b'CTPK'):
        handle(rel, None, b)
json.dump(idx, open(os.path.join(B, 'texidx.json'), 'w'), indent=0)
print(len(idx))
