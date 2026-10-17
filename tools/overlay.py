import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
B = os.path.join(os.path.dirname(__file__), '..')
M = json.load(open(os.path.join(B, 'rectmeta.json')))
A = json.load(open(os.path.join(B, 'all_rect.json'), encoding='utf-8'))
F = json.load(open(os.path.join(B, 'flag_rect.json'), encoding='utf-8'))
bytex = {}
for n in A: bytex.setdefault(M[n][0], []).append(n)
out = os.path.join(B, 'ov'); os.makedirs(out, exist_ok=True)
fnt = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 11)
order = []
for h, ns in sorted(bytex.items(), key=lambda x: M[x[1][0]][6]):
    a = np.array(Image.open(os.path.join(B, 'texdump', h + '.png')).convert('RGBA')).astype(np.float32)
    y, x = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    bg = ((((x // 8) + (y // 8)) % 2) * 30 + 50)[..., None]
    al = a[..., 3:4] / 255; c = a[..., :3] * al + bg * (1 - al)
    im = Image.fromarray(c.astype(np.uint8))
    s = max(1, min(4, 1400 // max(im.size)))
    im = im.resize((im.width * s, im.height * s), Image.NEAREST).convert('RGB')
    d = ImageDraw.Draw(im)
    for n in ns:
        _, k, rx, ry, rw, rh, e = M[n]
        col = (255, 60, 60) if n in F else (60, 200, 255)
        d.rectangle([rx * s, ry * s, (rx + rw) * s - 1, (ry + rh) * s - 1], outline=col)
        d.text((rx * s + 1, ry * s), str(k), font=fnt, fill=(255, 255, 0))
    p = '%02d_%s.png' % (len(order), h[:8]); im.save(os.path.join(out, p)); order.append([p, h, M[ns[0]][6], a.shape[1], a.shape[0], len(ns)])
json.dump(order, open(os.path.join(out, 'order.json'), 'w'), indent=0)
for o in order: print(o)
