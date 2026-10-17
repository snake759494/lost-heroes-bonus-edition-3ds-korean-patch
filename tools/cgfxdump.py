import glob, os, sys, struct, hashlib, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
from lz11 import comp_dec
from nbf import parse
import texdec as T
B = os.path.join(os.path.dirname(__file__), '..')
PICA = ['rgba8', 'rgb8', 'rgba5551', 'rgb565', 'rgba4', 'la8', 'hilo8', 'l8', 'a8', 'la4', 'l4', 'a4', 'etc1', 'etc1a4']
def txobs(d):
    p = 0
    while True:
        t = d.find(b'TXOB', p)
        if t < 0: return
        p = t + 4
        try:
            fmt, = struct.unpack_from('<I', d, t + 0x30)
            h, w, sz, off = struct.unpack_from('<IIII', d, t + 0x38)
        except struct.error: return
        if fmt >= len(PICA) or not (8 <= w <= 1024 and 8 <= h <= 1024): continue
        do = t + 0x44 + off
        yield t, PICA[fmt], w, h, do, sz
if __name__ == '__main__':
    out = os.path.join(B, 'cgdump'); os.makedirs(out, exist_ok=True)
    idx = {}
    pat = sys.argv[1] if len(sys.argv) > 1 else 'Graph/CutScene/**/*.cmp'
    for f in glob.glob(os.path.join(B, 'ext', 'romfs', pat), recursive=True):
        rel = os.path.relpath(f, os.path.join(B, 'ext', 'romfs')).replace(os.sep, '/')
        try: b = comp_dec(open(f, 'rb').read())
        except Exception: continue
        if b[:4] != b'2NBF': continue
        for n, u, d in parse(b)[1]:
            if d[:4] != b'CGFX': continue
            for t, fmt, w, h, do, sz in txobs(d):
                n0 = w * h * T.BPP[fmt] // 8
                raw = d[do:do + n0]
                if len(raw) < n0: continue
                hh = hashlib.md5(raw).hexdigest()
                r = idx.setdefault(hh, dict(fmt=fmt, w=w, h=h, refs=[]))
                r['refs'].append([rel, n, t])
                p = os.path.join(out, hh + '.png')
                if not os.path.exists(p):
                    try: Image.fromarray(T.decode(fmt, raw, w, h)).save(p)
                    except Exception as e: r['err'] = str(e)
    json.dump(idx, open(os.path.join(B, 'cgidx.json'), 'w'), indent=0)
    print(len(idx))
