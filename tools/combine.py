import pickle,numpy as np
V=pickle.load(open('votes.pkl','rb'));cands,S=pickle.load(open('tmpl.pkl','rb'))
ci={c:i for i,c in enumerate(cands)}
res={};unsure=[]
for g in range(363,2112):
    row=S[g-363];top=np.argsort(-row)[:5]
    vc=V.get(g)
    pick=None
    if vc:
        c,n=vc.most_common(1)[0];tot=sum(vc.values())
        ts=row[ci[c]] if c in ci else -1
        if n>=2 and n/tot>=0.6: pick=c
        elif ts>=0.55: pick=c
        elif c==cands[top[0]]: pick=c
    if pick is None:
        pick=cands[top[0]]
        unsure.append(g)
    res[g]=pick
print(len(unsure))
pickle.dump((res,unsure),open('comb.pkl','wb'))
