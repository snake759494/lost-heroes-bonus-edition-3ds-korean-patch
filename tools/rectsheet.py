import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
B = os.path.join(os.path.dirname(__file__), '..')
M = json.load(open(os.path.join(B, 'rectmeta.json')))
F = json.load(open(os.path.join(B, sys.argv[1]), encoding='utf-8'))
keys = sorted(F, key=lambda n: (M[n][6], M[n][0], M[n][1]))
fnt = ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc', 14)
out = os.path.join(B, sys.argv[2]); os.makedirs(out, exist_ok=True)
W = 1000; per = int(sys.argv[3]) if len(sys.argv) > 3 else 22
for p in range(0, len(keys), per):
    rows = []
    for n in keys[p:p + per]:
        h, k, x, y, w, hh, e = M[n]
        a = np.array(Image.open(os.path.join(B, 'texdump', h + '.png')).convert('RGBA')).astype(np.float32)[y:y + hh, x:x + w]
        al = a[..., 3:4] / 255; c = a[..., :3] * al + 60 * (1 - al)
        im = Image.fromarray(c.astype(np.uint8))
        s = max(1, min(4, 40 // max(1, hh)))
        im = im.resize((w * s, hh * s), Image.NEAREST)
        if im.width > 640: im = im.resize((640, max(1, im.height * 640 // im.width)))
        row = Image.new('RGB', (W, max(im.height, 34) + 4), (255, 255, 255))
        row.paste(im, (0, 2))
        d = ImageDraw.Draw(row)
        d.text((650, 0), n, font=fnt, fill=(0, 0, 200))
        d.text((650, 17), (F[n] or '')[:24], font=fnt, fill=(0, 0, 0))
        rows.append(row)
    H = sum(r.height for r in rows)
    pg = Image.new('RGB', (W, H), (200, 200, 200)); yy = 0
    for r in rows: pg.paste(r, (0, yy)); yy += r.height
    pg.save(os.path.join(out, 'r%03d.png' % (p // per)))
json.dump(keys, open(os.path.join(out, 'order.json'), 'w'))
print((len(keys) + per - 1) // per)
