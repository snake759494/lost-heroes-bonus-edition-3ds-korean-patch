import json,glob,os
B=os.path.join(os.path.dirname(__file__),'..')
U=json.load(open(os.path.join(B,'units.json'),encoding='utf-8'))
jp2ko={}
for f in sorted(glob.glob(os.path.join(B,'tr','in','*.json'))):
    o=os.path.join(B,'tr','out',os.path.basename(f))
    if not os.path.exists(o): continue
    I=json.load(open(f,encoding='utf-8'));O=json.load(open(o,encoding='utf-8'))
    for u in I:
        k=O.get(str(u['id']))
        if k is not None: jp2ko[u['jp']]=k
fx=os.path.join(B,'tr','fix.json')
if os.path.exists(fx):
    for j,k in json.load(open(fx,encoding='utf-8')).items(): jp2ko[j]=k
rp=os.path.join(B,'tr','replace.json')
if os.path.exists(rp):
    R=json.load(open(rp,encoding='utf-8'))
    for j in jp2ko:
        for a,b in R.items(): jp2ko[j]=jp2ko[j].replace(a,b)
cur={u['jp']:u['id'] for u in U}
json.dump({str(cur[j]):k for j,k in jp2ko.items() if j in cur},open(os.path.join(B,'ko_all.json'),'w',encoding='utf-8'),ensure_ascii=False)
