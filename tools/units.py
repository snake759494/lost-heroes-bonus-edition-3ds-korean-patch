import json, os, re, collections
B = os.path.join(os.path.dirname(__file__), '..')
A = json.load(open(os.path.join(B, 'all_jp.json'), encoding='utf-8'))
TOK = re.compile(r'\{([0-9a-f]{4})\}(　*)')
def tok(j):
    return TOK.sub(lambda m: '⟦%s%s⟧' % (m.group(1), ':%d' % len(m.group(2)) if m.group(2) else ''), j)
def linelen(s):
    return max(len(re.sub(r'⟦[^⟧]*⟧', lambda m: '　' * int(m.group(0)[6:-1]) if ':' in m.group(0) else '', l)) for l in s.split('\n'))
tabmax = collections.Counter()
for r, ti, si, j in A:
    tabmax[(r, ti)] = max(tabmax[(r, ti)], linelen(tok(j)))
units = collections.OrderedDict()
old = {u['jp']: u for u in json.load(open(os.path.join(B, 'units.json'), encoding='utf-8'))} if os.path.exists(os.path.join(B, 'units.json')) else {}
next_id = max([u['id'] for u in old.values()] + [-1]) + 1
refs = []
for r, ti, si, j in A:
    t = tok(j)
    if r.startswith('Table/Event'):
        w = 23; grp = r.rsplit('/', 1)[0]
    else:
        w = max(tabmax[(r, ti)], 4); grp = '%s#%d' % (r, ti)
    if t not in units:
        units[t] = dict(id=len(units), jp=t, w=w, ctx=grp, lines=t.count('\n') + 1)
    else:
        u = units[t]; u['w'] = min(u['w'], w)
    refs.append((r, ti, si, units[t]['id']))
json.dump(list(units.values()), open(os.path.join(B, 'units.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
json.dump(refs, open(os.path.join(B, 'refs.json'), 'w', encoding='utf-8'))
print(len(units))
