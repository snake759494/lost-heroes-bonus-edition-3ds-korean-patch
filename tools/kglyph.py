import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..') + '/'
_cache = {}
from fontTools.ttLib import TTFont
_cm = {}
def font(name, size, ch=None):
    if ch is not None:
        if name not in _cm: _cm[name] = TTFont(FD + name).getBestCmap()
        if ord(ch) not in _cm[name]:
            k = ('malgunbd', size)
            if k not in _cache: _cache[k] = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', size)
            return _cache[k]
    k = (name, size)
    if k not in _cache: _cache[k] = ImageFont.truetype(FD + name, size)
    return _cache[k]
def render(ch, cw, chh, box, name, size, thr_gamma=1.0):
    """render ch into cw x chh cell (L 0-255), glyph fitted into box=(x0,y0,w,h)"""
    x0, y0, bw, bh = box
    f = font(name, size, ch)
    im = Image.new('L', (cw * 4, chh * 4), 0)
    d = ImageDraw.Draw(im)
    l, t, r, b = d.textbbox((0, 0), ch, font=f)
    if r <= l:
        return np.zeros((chh, cw), np.uint8)
    # place by font ascent so baseline consistent; center horizontally
    asc, desc = f.getmetrics()
    ref = d.textbbox((0, 0), '한', font=f)
    rh = ref[3] - ref[1]
    ox = x0 + (bw - (r - l)) / 2.0 - l
    oy = y0 + (bh - rh) / 2.0 - ref[1]
    im = Image.new('L', (cw, chh), 0)
    ImageDraw.Draw(im).text((ox, oy), ch, font=f, fill=255)
    a = np.array(im, np.float32) / 255
    if thr_gamma != 1.0: a = a ** thr_gamma
    return (a * 255).astype(np.uint8)
def render_ss(ch, cw, chh, name, size, S=4, gam=0.8):
    f = font(name, size, ch); W, H = cw * S, chh * S
    im = Image.new('L', (W, H)); d = ImageDraw.Draw(im)
    ref = d.textbbox((0, 0), '한', font=f); l, t, r, b = d.textbbox((0, 0), ch, font=f)
    if r <= l: return np.zeros((chh, cw), np.uint8)
    ox = (W - (r - l)) / 2 - l; oy = (H - (ref[3] - ref[1])) / 2 - ref[1]
    d.text((ox, oy), ch, font=f, fill=255)
    x = np.array(im.resize((cw, chh), Image.BOX), np.float32) / 255
    x = np.clip(x / 0.75, 0, 1) ** gam
    return (x * 255).astype(np.uint8)
