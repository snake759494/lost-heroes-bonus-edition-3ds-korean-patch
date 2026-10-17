# Build Korean-logo target frames for the opening movie ending logo
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from ycc import load, to_rgb, from_rgb, save, W, H
B = os.path.join(os.path.dirname(__file__), '..')
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..') + '/'
REF = 2940; X0, Y0, X1, Y1 = 56, 80, 308, 136
F0, F1 = int(sys.argv[1]), int(sys.argv[2])
ref = load(REF)
rgb = to_rgb(*ref).astype(float)
reg = rgb[Y0:Y1, X0:X1]
L = reg.mean(-1)
fill = np.median(reg[L > np.percentile(L, 93)], 0)
glow = np.median(reg[(L > np.percentile(L, 70)) & (L < np.percentile(L, 85))], 0)
bg = np.median(rgb[Y0 - 8:Y0 - 2, X0:X1].reshape(-1, 3), 0)
new = rgb.copy()
hue = reg[..., 1] - (reg[..., 0] + reg[..., 2]) / 2
em = (hue > 12) | (L > 90)
em = np.array(Image.fromarray((em * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.2)), np.float32)[..., None] / 255
new[Y0:Y1, X0:X1] = reg * (1 - em) + bg * em
# soft edge blend of erased area
S = 4
txt = '로스트 히어로즈'
f = ImageFont.truetype(FD + 'NanumSquareNeo-eHv.ttf', 40 * S)
bw, bh = 226, 38
im = Image.new('L', (bw * S * 2, bh * S * 2)); d = ImageDraw.Draw(im)
bb = d.textbbox((0, 0), txt, font=f)
d.text((-bb[0] + 4, -bb[1] + 4), txt, font=f, fill=255)
m = np.array(im, np.float32)
ys, xs = np.nonzero(m > 10); m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
m = np.array(Image.fromarray(m.astype(np.uint8)).resize((bw, bh), Image.LANCZOS), np.float32) / 255
mask = np.zeros((H, W), np.float32); mask[95:95 + bh, 70:70 + bw] = m
g1 = np.array(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), np.float32) / 255
g1 = np.clip(g1 * 1.8, 0, 1)
for c in range(3):
    new[..., c] = new[..., c] * (1 - g1) + glow[c] * g1
    new[..., c] = new[..., c] * (1 - mask) + fill[c] * mask
Image.fromarray(np.clip(new, 0, 255).astype(np.uint8)).save(os.path.join(B, 'movlogo_preview.png'))
K = from_rgb(np.clip(new, 0, 255))
# keep original outside the region (avoid chroma resampling drift)
Kd = []
for pl, (a, b) in enumerate(zip(K, ref)):
    sc = 1 if pl == 0 else 2
    out = b.copy(); y0, y1, x0, x1 = Y0 // sc - 1, Y1 // sc + 1, X0 // sc - 1, X1 // sc + 1
    out[y0:y1, x0:x1] = a[y0:y1, x0:x1]
    Kd.append(out - b)
os.makedirs(os.path.join(B, 'tgt'), exist_ok=True)
rm = ref[0][Y0:Y1, X0:X1].mean()
for i in range(F0, F1 + 1):
    fr = load(i)
    k = min(1.0, max(0.0, fr[0][Y0:Y1, X0:X1].mean() / rm)) if i < REF - 15 or i > REF + 90 else 1.0
    save(*[p + k * dd for p, dd in zip(fr, Kd)], os.path.join(B, 'tgt', '%05d.yuv' % i))
print('frames', F0, F1)
