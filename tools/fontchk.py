import sys, glob, os
from fontTools.ttLib import TTFont
B = os.path.join(os.path.dirname(__file__), '..')
cm = TTFont(os.path.join(B, '..', 'NanumSquareNeo-dEb.ttf')).getBestCmap()
sys.stdout = open(os.path.join(B, 'o.txt'), 'w', encoding='utf-8')
for f in glob.glob(os.path.join(B, 'spec_*.txt')) + [os.path.join(B, 'img_spec.txt')]:
    for l in open(f, encoding='utf-8'):
        p = l.split('|')
        if len(p) > 1:
            t = p[1].strip().replace(chr(92) + 'n', '').replace('・', '·')
            bad = [c for c in t if ord(c) not in cm]
            if bad: print(os.path.basename(f), repr(bad), t[:40])
