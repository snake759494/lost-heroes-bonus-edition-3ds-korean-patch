# Insert imgout/<md5>.png textures into every pack that references them (writes into build/romfs)
import json, os, sys, collections
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
from lz11 import comp_dec, comp_enc
from nbf import parse, build as nbuild
from ctpk import textures
import imgenc as E
B = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
I = json.load(open(os.path.join(B, 'texidx.json')))
ROM = os.path.join(B, 'ext', 'romfs'); OUT = os.path.join(B, 'build', 'romfs')
bypack = collections.defaultdict(list)
n = 0
for f in os.listdir(os.path.join(B, 'imgout')):
    h = f[:-4]
    if h not in I: continue
    enc = None
    for p, e, ti in I[h]['refs']:
        if e is None: continue
        bypack[p].append((e, ti, h))
    n += 1
cache = {}
def encoded(h):
    if h not in cache:
        img = np.array(Image.open(os.path.join(B, 'imgout', h + '.png')).convert('RGBA'))
        cache[h] = E.encode(I[h]['fmt'], img[::-1].copy())
    return cache[h]
for p, items in bypack.items():
    src = os.path.join(OUT, p) if os.path.exists(os.path.join(OUT, p)) else os.path.join(ROM, p)
    b = comp_dec(open(src, 'rb').read())
    hdr, ents, o = parse(b)
    for e, ti, h in items:
        for ent in ents:
            if ent[0] != e: continue
            d = bytearray(ent[2]); t = textures(bytes(d))[ti]
            raw = encoded(h)
            assert len(raw) <= t['size'], (p, e, len(raw), t['size'])
            d[t['pos']:t['pos'] + len(raw)] = raw
            ent[2] = bytes(d)
    dst = os.path.join(OUT, p); os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(comp_enc(nbuild(hdr, ents, o)))
print('textures', n, 'packs', len(bypack))
