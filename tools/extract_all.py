import sys, glob, os, json, collections
sys.path.insert(0, os.path.dirname(__file__))
from mbbw import parse_full
def parse(d):
    return [(t[0], [x if isinstance(x, list) else None for x in t[1]] if t[0]=='MTBL' else None) for t in parse_full(d)[1]]
from jdec import dec
B = os.path.join(os.path.dirname(__file__), '..')
sys.stdout = open(os.path.join(B, 'o.txt'), 'w', encoding='utf-8')
out = []; uniq = collections.OrderedDict(); ctrl = collections.Counter(); utf = set()
root = os.path.join(B, 'ext', 'romfs')
for f in sorted(glob.glob(os.path.join(root, '**', '*.mbb'), recursive=True)):
    rel = os.path.relpath(f, root).replace(os.sep, '/')
    for ti, (k, t) in enumerate(parse(open(f, 'rb').read())):
        if k != 'MTBL': continue
        for si, s in enumerate(t):
            if not s: continue
            if any(0x2000 <= v < 0x8000 for v in s): utf.add(rel); continue
            for v in s:
                if v > 2112: ctrl[v] += 1
            j = dec(s); out.append((rel, ti, si, j)); uniq[j] = uniq.get(j, 0) + 1
print(len(out), len(uniq), sum(len(u) for u in uniq))
print(utf)
print([(hex(k), n) for k, n in ctrl.most_common(60)])
json.dump(out, open(os.path.join(B, 'all_jp.json'), 'w', encoding='utf-8'), ensure_ascii=False)
grp = collections.Counter(); gu = collections.defaultdict(set)
for r, _, _, j in out:
    g = '/'.join(r.split('/')[:2]); gu[g].add(j)
for g in gu: grp[g] = sum(len(x) for x in gu[g])
print(grp.most_common())
