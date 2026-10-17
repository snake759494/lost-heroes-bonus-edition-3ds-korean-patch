# Render Korean replacements into dumped textures according to img_spec.txt
import json, os, sys, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
B = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..') + '/'
FONTS = {'bold': 'NanumSquareNeo-cBd.ttf', 'heavy': 'NanumSquareNeo-eHv.ttf', 'xb': 'NanumSquareNeo-dEb.ttf',
         'reg': 'NanumSquareNeo-bRg.ttf', 'serif': 'SeoulHangangEB.ttf', 'serifm': 'SeoulHangangM.ttf'}
I = json.load(open(os.path.join(B, 'texidx.json')))
UV = json.load(open(os.path.join(B, 'uv.json')))
_fc = {}
def font(n, s):
    k = (n, s)
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + FONTS[n], s)
    return _fc[k]

def parse_spec(path):
    tex = {}; cur = None
    for ln in open(path, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if not ln.strip() or ln.lstrip().startswith('#'): continue
        if ln.startswith('@'):
            cur = ln[1:].split()[0]; tex.setdefault(cur, []); continue
        parts = [p.strip() for p in ln.split('|')]
        tex[cur].append(parts)
    return tex

def lum(c): return c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114

opts_glob = {}
def analyze(crop, tex_transparent=False):
    """crop RGBA float; returns style dict"""
    a = crop[..., 3]; rgb = crop[..., :3]; L = lum(rgb)
    H, W = a.shape
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    transparent = tex_transparent or (border < 60).mean() > 0.6 or (a < 60).mean() > 0.25
    st = dict(transparent=transparent)
    if transparent:
        m = a > 140
        if m.sum() < 3: m = a > 40
        if m.sum() == 0: return None
        Lm = L[m]; hi = np.percentile(Lm, 60); lo = np.percentile(Lm, 15)
        fm = m & (L >= hi)
        st['fill_rows'] = row_colors(rgb, fm)
        om = m & (L <= lo)
        if Lm.max() - lo > 70 and om.sum() > 0:
            st['out'] = np.median(rgb[om], 0); st['ow'] = 1
            # outline thickness guess: fraction of dark pixels
            if om.sum() > 1.2 * fm.sum(): st['ow'] = 2
        ys, xs = np.nonzero(m)
        st['bbox'] = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    else:
        # opaque background: text = pixels far from local median
        med = np.array(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(7)), np.float32)
        d = np.abs(lum(med) - L)
        brd = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        if brd.std(0).max() < 22:
            bgc = np.median(brd, 0)
            d = np.abs(rgb - bgc).max(-1)
            med = np.broadcast_to(bgc, rgb.shape).astype(np.float32)
        tm = d > float(opts_glob.get('thr', 22))
        if tm.sum() < 3: return None
        bright = (L > lum(med))[tm].mean() > 0.5
        sel = tm & ((L > lum(med)) if bright else (L < lum(med)))
        st['fill_rows'] = row_colors(rgb, sel)
        # outline: opposite-direction strong pixels
        opp = tm & ~sel
        if opp.sum() > 0.3 * sel.sum():
            st['out'] = np.median(rgb[opp], 0); st['ow'] = 1
        ys, xs = np.nonzero(tm)
        st['bbox'] = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        st['tmask'] = tm
    return st

def row_colors(rgb, m):
    H = m.shape[0]; out = np.zeros((H, 3), np.float32)
    allc = np.median(rgb[m], 0) if m.sum() else np.array([255, 255, 255], np.float32)
    for y in range(H):
        r = m[y]
        out[y] = np.median(rgb[y][r], 0) if r.sum() >= 2 else allc
    # smooth
    k = np.ones(3) / 3
    for c in range(3): out[:, c] = np.convolve(np.pad(out[:, c], 1, mode='edge'), k, 'valid')
    return out

def inpaint(img, mask, it=40):
    """fill masked pixels of RGBA float img by iterative neighbor averaging"""
    img = img.copy(); m = mask.copy()
    m = np.array(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    known = ~m
    for _ in range(it):
        if known.all(): break
        acc = np.zeros_like(img); cnt = np.zeros(img.shape[:2], np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                sh = np.roll(np.roll(img * known[..., None], dy, 0), dx, 1)
                kn = np.roll(np.roll(known, dy, 0), dx, 1)
                acc += sh; cnt += kn
        new = (~known) & (cnt > 0)
        img[new] = acc[new] / cnt[new][:, None]
        known = known | new
    return img

def text_layer(text, fontname, th, maxw, ow, spacing=0, S=4):
    """render text mask at supersample; returns (fill_mask, outline_mask) float arrays at 1x, size fitted"""
    lines = text.split('\\n')
    best = None
    size = int(th * S * 1.25)
    for _ in range(40):
        f = font(fontname, max(4, size))
        ref = f.getbbox('한')
        lh = ref[3] - ref[1]
        ws = [f.getlength(l) + spacing * S * max(0, len(l) - 1) for l in lines]
        W = int(max(ws) + 8 * S); H = int(lh * len(lines) + (len(lines) - 1) * lh * 0.25 + 8 * S)
        best = (f, ref, lh, ws, W, H)
        if lh <= th * S * len(lines) + 1: break
        size -= 1
    f, ref, lh, ws, W, H = best
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    y = 4 * S - ref[1]
    for l, w in zip(lines, ws):
        if spacing:
            x = 4 * S
            for ch in l:
                d.text((x, y), ch, font=f, fill=255); x += f.getlength(ch) + spacing * S
        else:
            d.text((4 * S, y), l, font=f, fill=255)
        y += lh * 1.25
    a = np.array(im, np.float32) / 255
    ys, xs = np.nonzero(a > 0.05)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return a

def draw_text(canvas, box, text, st, opts):
    x0, y0, bw, bh = box
    fontname = opts.get('font', 'xb')
    if st and 'bbox' in st and 'h' not in opts:
        bx0, by0, bx1, by1 = st['bbox']
        th = by1 - by0
        if '\\n' in text: th = th / (text.count('\\n') + 1) * 0.9
    else:
        th = float(opts.get('h', bh * 0.8))
        bx0, by0, bx1, by1 = 0, int((bh - th) / 2), bw, int((bh + th) / 2)
    th = max(5, th)
    ow = int(opts.get('ow', st.get('ow', 0) if st and 'out' in st else 0))
    S = 4
    a = text_layer(text, fontname, th, bw, ow, float(opts.get('sp', 0)), S)
    nl = text.count('\\n') + 1
    tgt_h = int(round(th * nl + (nl - 1) * th * 0.25)) if nl > 1 else int(round(th))
    tgt_h = min(tgt_h, bh - 2 * ow) if bh > 2 * ow + 3 else tgt_h
    sc = tgt_h / a.shape[0]
    tw = a.shape[1] * sc
    avail = bw - 2 * ow - int(opts.get('pad', 1)) * 2
    if tw > avail:
        tw = avail
    tw = max(1, int(round(tw)))
    m = np.array(Image.fromarray((a * 255).astype(np.uint8)).resize((tw, tgt_h), Image.LANCZOS), np.float32) / 255
    m = np.clip(m * float(opts.get('gain', 1.15)), 0, 1)
    al = opts.get('al', 'l' if (st and st.get('transparent')) else 'c')
    if al == 'l': px = x0 + max(ow + 1, bx0 if st else 0)
    elif al == 'r': px = x0 + bw - ow - 1 - tw
    else: px = x0 + (bw - tw) // 2
    if 'y' in opts: py = y0 + int(opts['y'])
    else: py = y0 + int(round(((by0 + by1) - tgt_h) / 2)) if st else y0 + (bh - tgt_h) // 2
    py = max(y0, min(py, y0 + bh - tgt_h))
    # fill color per row
    if 'fill' in opts:
        fc = np.array([int(opts['fill'][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
        rows = np.tile(fc, (tgt_h, 1))
    elif st and 'fill_rows' in st:
        fr = st['fill_rows']; src = np.linspace(by0, by1 - 1, tgt_h).clip(0, len(fr) - 1)
        rows = fr[src.astype(int)]
    else:
        rows = np.tile(np.array([255, 255, 255], np.float32), (tgt_h, 1))
    oc = None
    if 'out' in opts: oc = np.array([int(opts['out'][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
    elif st and 'out' in st: oc = st['out']
    H, W = canvas.shape[:2]
    pad = ow + 1
    M = np.zeros((tgt_h + 2 * pad, tw + 2 * pad), np.float32); M[pad:pad + tgt_h, pad:pad + tw] = m
    if oc is not None and ow > 0:
        O = np.array(Image.fromarray((M * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * ow + 1)), np.float32) / 255
    else:
        O = None
    FC = np.zeros((tgt_h + 2 * pad, tw + 2 * pad, 3), np.float32); FC[:] = rows.mean(0)
    FC[pad:pad + tgt_h] = rows[:, None, :]
    for yy in range(M.shape[0]):
        Y = py - pad + yy
        if Y < 0 or Y >= H: continue
        for xx in range(M.shape[1]):
            X = px - pad + xx
            if X < 0 or X >= W or X < x0 or X >= x0 + bw or Y < y0 or Y >= y0 + bh: continue
            f = M[yy, xx]; o = O[yy, xx] if O is not None else 0
            if f <= 0 and o <= 0: continue
            dst = canvas[Y, X]
            if O is not None and o > 0:
                a_ = o; col = oc
                dst[:3] = dst[:3] * (1 - a_) + col * a_ if dst[3] > 0 else col
                dst[3] = max(dst[3], a_ * 255)
            if f > 0:
                col = FC[yy, xx]
                dst[:3] = (dst[:3] * (1 - f) + col * f) if dst[3] > 0 else col
                dst[3] = max(dst[3], f * 255)

def boxes_for(h, key):
    r = I[h]; rs = UV.get(r['name'].lower().rsplit('.', 1)[0]) or [[0, 0, r['w'], r['h']]]
    if re.fullmatch(r'\d+', key): return tuple(rs[int(key)])
    return tuple(int(v) for v in key.split(','))

def process(h8, ops):
    h = [k for k in I if k.startswith(h8)][0]
    img = np.array(Image.open(os.path.join(B, 'texdump', h + '.png')).convert('RGBA')).astype(np.float32)
    orig = img.copy()
    jobs = []
    texT = (orig[..., 3] < 60).mean() > 0.2
    owned = np.zeros(orig.shape[:2], bool)
    r_ = I[h]; jb = set(boxes_for(h, op[0]) for op in ops)
    for rb in (UV.get(r_['name'].lower().rsplit('.', 1)[0]) or []):
        if tuple(rb) in jb: continue
        x_, y_, w_, h_ = rb; owned[y_:y_ + h_, x_:x_ + w_] = True
    for op in ops:
        box = boxes_for(h, op[0])
        text = op[1] if len(op) > 1 else ''
        opts = dict(o.split('=', 1) for o in op[2].split(',')) if len(op) > 2 and op[2] else {}
        x, y, w, hh = box
        crop = orig[y:y + hh, x:x + w]
        opts_glob.clear(); opts_glob.update(opts)
        st = analyze(crop, texT and opts.get('bg') != 'opaque') if crop.size else None
        jobs.append((box, text, st, opts))
    # clear
    for box, text, st, opts in jobs:
        if opts.get('keep'): continue
        x, y, w, hh = box
        if st is None: continue
        if st['transparent']:
            img[y:y + hh, x:x + w] = 0
            # residual 1px fringe outside the rect that belongs to no other (untouched) rect
            Hh, Ww = img.shape[:2]
            for (yy, xx) in [(y - 1, None), (y + hh, None), (None, x - 1), (None, x + w)]:
                if yy is not None and 0 <= yy < Hh:
                    for X in range(max(0, x), min(Ww, x + w)):
                        if not owned[yy, X]: img[yy, X] = 0
                if xx is not None and 0 <= xx < Ww:
                    for Y in range(max(0, y), min(Hh, y + hh)):
                        if not owned[Y, xx]: img[Y, xx] = 0
        else:
            mg = int(opts.get('mg', 2))
            Hh, Ww = img.shape[:2]
            X0, Y0, X1, Y1 = max(0, x - mg), max(0, y - mg), min(Ww, x + w + mg), min(Hh, y + hh + mg)
            sub = img[Y0:Y1, X0:X1]
            rgb = sub[..., :3]
            op = sub[..., 3] > 200
            brd = np.concatenate([rgb[0][op[0]], rgb[-1][op[-1]], rgb[:, 0][op[:, 0]], rgb[:, -1][op[:, -1]]])
            if len(brd) == 0: brd = np.zeros((1, 3), np.float32)
            bm = np.median(brd, 0)
            if (np.abs(brd - bm).max(-1) < 20).mean() > 0.7:
                bgc = np.concatenate([bm, [255.0]]).astype(np.float32)
                tm = np.abs(rgb - bgc[:3]).max(-1) > float(opts.get('thr', 22))
                tm = np.array(Image.fromarray((tm * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
                tm &= sub[..., 3] > 200
                sub[tm] = bgc
                img[Y0:Y1, X0:X1] = sub
                continue
            else:
                tm = np.zeros(sub.shape[:2], bool); tm[y - Y0:y - Y0 + hh, x - X0:x - X0 + w] = st['tmask']
            img[Y0:Y1, X0:X1] = inpaint(sub, tm)
    for box, text, st, opts in jobs:
        if text and text != '-':
            draw_text(img, box, text, st, opts)
    out = os.path.join(B, 'imgout'); os.makedirs(out, exist_ok=True)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(os.path.join(out, h + '.png'))
    return h

if __name__ == '__main__':
    spec = parse_spec(os.path.join(B, sys.argv[1] if len(sys.argv) > 1 else 'img_spec.txt'))
    only = set(sys.argv[2:])
    for h8, ops in spec.items():
        if only and h8 not in only: continue
        process(h8, ops)
    print('done', len(spec))
