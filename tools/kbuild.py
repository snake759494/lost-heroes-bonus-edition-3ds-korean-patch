# Build Korean romfs replacement files: MBBs + fonts
import json, os, sys, re, glob, collections, struct
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
from mbbw import parse_full, build as mbuild
from lz11 import comp_dec, comp_enc
from gfpt import textures
from nbf import parse as nparse, build as nbuild
from tex import untile4, tile4
from kglyph import render, render_ss
from wrap import rewrap
B = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROM = os.path.join(B, 'ext', 'romfs')
OUT = os.path.join(B, 'build', 'romfs')
log = open(os.path.join(B, 'build_log.txt'), 'w', encoding='utf-8')

base = open(os.path.join(B, 'base363.txt'), encoding='utf-8').read()
base = base[:328] + '！' + base[329:]
CODE = {}
for i, c in enumerate(base):
    if c not in CODE: CODE[c] = i + 1
# preferred mappings for half-width input
ALIAS = {'　': ' ', '･': '・', '！': '!', '？': '?', '～': '~'}
for c in range(0x21, 0x7c): CODE[chr(c)] = 233 + (c - 0x21) + 1
CODE['}'] = 325; CODE['~'] = 326
CODE[' '] = 235  # cell 234 = half-width space
for c in range(0xFF01, 0xFF5B):
    if chr(c - 0xFEE0) in CODE and chr(c) not in ALIAS: ALIAS[chr(c)] = chr(c - 0xFEE0)

units = {u['id']: u for u in json.load(open(os.path.join(B, 'units.json'), encoding='utf-8'))}
ko = {int(k): v for k, v in json.load(open(os.path.join(B, 'ko_all.json'), encoding='utf-8')).items()}
nw = 0
for i, u in units.items():
    if i in ko and u['ctx'].startswith('Table/Event'):
        ml = max(2, max(p.strip(chr(10)).count(chr(10)) + 1 for p in u['jp'].split('⟦8002⟧')))
        r, good = rewrap(ko[i], 336, ml)
        if not good: nw += 1; print('wrap overflow', i, repr(r), file=log)
        ko[i] = r
refs = [x for x in json.load(open(os.path.join(B, 'refs.json'), encoding='utf-8')) if not x[0].startswith(('Table/StaffRoll', 'Table/TestData'))]
TOKR = re.compile(r'⟦([0-9a-f]{4})(?::(\d+))?⟧')

def norm(c):
    return ALIAS.get(c, c)
# collect chars + frequency
freq = collections.Counter()
for r, ti, si, uid in refs:
    t = ko.get(uid)
    if t is None: continue
    for c in TOKR.sub('', t).replace('\n', ''):
        c = norm(c)
        if c not in CODE: freq[c] += 1
newchars = [c for c, _ in freq.most_common()]
MAXG = 2304
if 363 + len(newchars) > MAXG: raise SystemExit('too many glyphs %d' % len(newchars))
for i, c in enumerate(newchars): CODE[c] = 363 + i + 1
print('new glyphs', len(newchars), 'font10 overflow', max(0, 363 + len(newchars) - 2100), file=log)

def encode(t):
    out = []; p = 0
    for m in TOKR.finditer(t):
        out += enc_plain(t[p:m.start()])
        out.append(int(m.group(1), 16))
        if m.group(2): out += [1] * int(m.group(2))
        p = m.end()
    out += enc_plain(t[p:])
    return out
def enc_plain(s):
    o = []
    for c in s:
        if c == '\n': o.append(0x8001); continue
        o.append(CODE[norm(c)])
    return o

# ---- MBB
bad = 0
bymbb = collections.defaultdict(dict)
for r, ti, si, uid in refs: bymbb[r][(ti, si)] = uid
for rel, mp in bymbb.items():
    src = os.path.join(ROM, rel)
    hdr, tabs = parse_full(open(src, 'rb').read())
    changed = False
    for (ti, si), uid in mp.items():
        t = ko.get(uid)
        if t is None: continue
        try:
            tabs[ti][1][si] = encode(t); changed = True
        except KeyError as e:
            bad += 1; print('enc fail', rel, ti, si, repr(t), e, file=log)
    if changed:
        dst = os.path.join(OUT, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(mbuild(hdr, tabs))
print('mbb done, enc fails', bad, 'translated units', len(ko), '/', len(units), file=log)

# ---- fonts
FONTS = [('Font14', 14, 16, (0, 1, 13, 13), 'NanumSquareNeo-cBd.ttf', 13),
         ('Font10', 10, 10, (0, 0, 10, 10), 'NanumSquareNeo-cBd.ttf', 40)]
def chars_by_index():
    inv = {}
    for c, k in CODE.items():
        if k - 1 >= 363: inv[k - 1] = c
    return inv
inv = chars_by_index()
for name, cw, chh, box, fname, size in FONTS:
    d = bytearray(comp_dec(open(os.path.join(ROM, 'Font', name + '.cmp'), 'rb').read())); FONTDATA = globals().setdefault('FONTDATA', {})
    tx = textures(d)
    per = (256 // cw) * (512 // chh)
    imgs = [untile4(bytes(d[t['pos']:t['pos'] + t['size']]), 256, 512).copy() for t in tx]
    ncell = per * len(tx)
    for idx in range(363, ncell):
        ti, k = divmod(idx, per); r, c = divmod(k, 256 // cw)
        ch = inv.get(idx)
        g = (render_ss(ch, cw, chh, fname, size, gam=0.6) if cw == 10 else render(ch, cw, chh, box, fname, size)) if ch else np.zeros((chh, cw), np.uint8)
        imgs[ti][r * chh:(r + 1) * chh, c * cw:(c + 1) * cw] = g
    for t, im in zip(tx, imgs):
        d[t['pos']:t['pos'] + t['size']] = tile4(im)
    dst = os.path.join(OUT, 'Font', name + '.cmp'); os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(comp_enc(bytes(d))); FONTDATA['Font/%s.tpc' % name] = bytes(d)
    Image.fromarray(np.hstack(imgs)).save(os.path.join(B, 'build', name + '_ko.png'))
json.dump({c: k for c, k in CODE.items()}, open(os.path.join(B, 'build', 'codes.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('fonts done', file=log)

# ---- packs containing copies
packs = json.load(open(os.path.join(B, 'packs.json')))
np_ = 0
for prel, names in packs.items():
    b = comp_dec(open(os.path.join(ROM, prel), 'rb').read())
    h, ents, o = nparse(b); ch = False
    for e in ents:
        n = e[0].replace(chr(92), '/')
        if n in FONTDATA: e[2] = FONTDATA[n]; ch = True; continue
        built = os.path.join(OUT, n)
        if '/' not in n and n.lower().endswith('.mbb'):
            cand = glob.glob(os.path.join(OUT, 'Table', '**', n), recursive=True)
            if len(cand) == 1: built = cand[0]
        if n.lower().endswith('.mbb') and os.path.exists(built):
            e[2] = open(built, 'rb').read(); ch = True
    if ch:
        dst = os.path.join(OUT, prel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(comp_enc(nbuild(h, ents, o))); np_ += 1
print('packs rebuilt', np_, file=log)
