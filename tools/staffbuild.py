# Korean staff roll: rebuild FontStaff glyph sheet (17 cols x 32 rows, 256/17 x 16 cells) and StaffRoll.mbb
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from lz11 import comp_dec, comp_enc
from gfpt import textures
from tex import untile4, tile4
from mbbw import parse_full, build as mbuild
from nbf import parse as nparse, build as nbuild
B = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROM = os.path.join(B, 'ext', 'romfs'); OUT = os.path.join(B, 'build', 'romfs')
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..') + '/'
ko = json.load(open(os.path.join(B, 'tr', 'staff_ko.json'), encoding='utf-8'))
chars = [' ', '*']
for k in sorted(ko, key=int):
    for c in ko[k]:
        if c not in chars: chars.append(c)
CW = 256 / 17; NC = 17 * 32
assert len(chars) <= NC, len(chars)
code = {c: i + 1 for i, c in enumerate(chars)}
d = bytearray(comp_dec(open(os.path.join(ROM, 'Font', 'FontStaff.cmp'), 'rb').read()))
t = textures(bytes(d))[0]
img = np.zeros((512, 256), np.uint8)
S = 4
f = ImageFont.truetype(FD + 'SeoulHangangEB.ttf', 14 * S)
fl = ImageFont.truetype(FD + 'SeoulHangangB.ttf', 14 * S)
for i, c in enumerate(chars):
    if c == ' ': continue
    r, col = divmod(i, 17)
    x0 = int(round(col * CW)); y0 = r * 16
    im = Image.new('L', (15 * S, 16 * S)); dr = ImageDraw.Draw(im)
    ff = f if ord(c) >= 0x1100 else fl
    ref = dr.textbbox((0, 0), '한', font=ff); bb = dr.textbbox((0, 0), c, font=ff)
    ox = (15 * S - (bb[2] - bb[0])) / 2 - bb[0]; oy = (16 * S - (ref[3] - ref[1])) / 2 - ref[1]
    dr.text((ox, oy), c, font=ff, fill=255)
    g = np.array(im.resize((15, 16), Image.BOX), np.float32) / 255
    g = (np.clip(g / 0.8, 0, 1) * 255).astype(np.uint8)
    img[y0:y0 + 16, x0:x0 + 15] = np.maximum(img[y0:y0 + 16, x0:x0 + 15], g)
d[t['pos']:t['pos'] + t['size']] = tile4(img)
os.makedirs(os.path.join(OUT, 'Font'), exist_ok=True)
open(os.path.join(OUT, 'Font', 'FontStaff.cmp'), 'wb').write(comp_enc(bytes(d)))
Image.fromarray(img).save(os.path.join(B, 'build', 'FontStaff_ko.png'))
rel = 'Table/StaffRoll/StaffRoll.mbb'
hdr, tabs = parse_full(open(os.path.join(ROM, rel), 'rb').read())
for k, v in ko.items():
    tabs[0][1][int(k)] = [code[c] for c in v]
mb = mbuild(hdr, tabs)
os.makedirs(os.path.dirname(os.path.join(OUT, rel)), exist_ok=True)
open(os.path.join(OUT, rel), 'wb').write(mb)
# copies inside packs
packs = json.load(open(os.path.join(B, 'packs.json')))
for p, names in packs.items():
    if not any(n.replace(chr(92), '/') == rel for n in names): continue
    src = os.path.join(OUT, p) if os.path.exists(os.path.join(OUT, p)) else os.path.join(ROM, p)
    h, e, o = nparse(comp_dec(open(src, 'rb').read()))
    for x in e:
        if x[0].replace(chr(92), '/') == rel: x[2] = mb
    open(os.path.join(OUT, p), 'wb').write(comp_enc(nbuild(h, e, o)))
    print('pack', p)
print('staff glyphs', len(chars))
