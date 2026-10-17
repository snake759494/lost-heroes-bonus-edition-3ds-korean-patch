import json, glob, os, sys, re, collections
B = os.path.join(os.path.dirname(__file__), '..')
sys.stdout = open(os.path.join(B, 'o.txt'), 'w', encoding='utf-8')
U = {u['id']: u for u in json.load(open(os.path.join(B, 'units.json'), encoding='utf-8'))}
ko = {int(k): v for k, v in json.load(open(os.path.join(B, 'ko_all.json'), encoding='utf-8')).items()}
gl = json.load(open(os.path.join(B, 'tr', 'glossary.json'), encoding='utf-8'))
# canonical from CharacterName tables
canon = {}
for u in U.values():
    if 'CharacterName' in u['ctx'] and u['id'] in ko and len(u['jp']) >= 2:
        canon.setdefault(u['jp'], ko[u['id']])
for j, k in gl.items(): canon.setdefault(j, k)
miss = collections.defaultdict(list)
for u in U.values():
    if 'CharacterName' in u['ctx'] or u['id'] not in ko: continue
    for j, k in canon.items():
        if len(j) >= 3 and j in u['jp']:
            kk = re.sub(r'\s', '', k)
            if kk not in re.sub(r'\s', '', ko[u['id']]): miss[j].append(u['id'])
for j, ids in sorted(miss.items(), key=lambda x: -len(x[1])):
    print('%s => %s  (%d)' % (j, canon[j], len(ids)))
    for i in ids[:3]: print('    ', ko[i].replace('\n', ' / ')[:70])
