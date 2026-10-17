import json, os, sys, collections, re
B = os.path.join(os.path.dirname(__file__), '..')
sys.stdout = open(os.path.join(B, 'o.txt'), 'w', encoding='utf-8')
A = json.load(open(os.path.join(B, 'all_jp.json'), encoding='utf-8'))
mx = collections.defaultdict(collections.Counter)
for r, ti, si, j in A:
    g = '/'.join(r.split('/')[:2]) if not r.startswith('Table/Event') else r.rsplit('/', 1)[0]
    for ln in j.split('\n'):
        mx[g][len(re.sub(r'\{[0-9a-f]+\}', '', ln))] += 1
for g, c in sorted(mx.items()):
    ks = sorted(c); tot = sum(c.values())
    acc = 0; p99 = None
    for k in ks:
        acc += c[k]
        if p99 is None and acc >= tot * 0.99: p99 = k
    print(g, 'max', ks[-1], 'p99', p99, 'n', tot)
seen = collections.Counter()
for r, ti, si, j in A:
    for m in re.findall(r'\{(8[0-9a-f]{3}|[af]000)\}', j):
        if seen[m] < 3:
            seen[m] += 1; print(m, r, ti, si, repr(j[:80]))
