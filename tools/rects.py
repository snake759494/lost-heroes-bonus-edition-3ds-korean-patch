import json,sys
I=json.load(open('texidx.json'));UV=json.load(open('uv.json'))
for p in sys.argv[1:]:
    h=[k for k in I if k.startswith(p)][0];r=I[h]
    rs=UV.get(r['name'].lower().rsplit('.',1)[0])
    print(p,r['name'],r['w'],r['h'],r['fmt'],[(i,)+tuple(x) for i,x in enumerate(rs or [])])
