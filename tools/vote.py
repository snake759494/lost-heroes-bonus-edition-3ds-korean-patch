import pickle,re,collections,unicodedata
segs=pickle.load(open('segs.pkl','rb'))
base=open('base363.txt',encoding='utf-8').read()
V=collections.defaultdict(collections.Counter)
nm=0
def nf(c): return unicodedata.normalize('NFKC',c)
for line in open('ocr.tsv',encoding='utf-8'):
    fn,_,txt=line.rstrip('\n').partition('\t')
    i=int(fn[:5]);s=segs[i]
    t=''.join(re.sub(r' @[\d,\-]+$','',p) for p in txt.split(' | '))
    t=t.replace(' ','')
    if len(t)!=len(s): continue
    # check known chars agree
    ok=True;known=0
    for g,c in zip(s,t):
        if g<363 and g not in (0,):
            known+=1
            if nf(base[g])!=nf(c): ok=False;break
    if not ok: continue
    nm+=1
    w=1+known*0.2
    for g,c in zip(s,t):
        if g>=363: V[g][c]+=w
res={}
for g in range(363,2112):
    if V[g]: c,n=V[g].most_common(1)[0];tot=sum(V[g].values());res[g]=(c,n,tot)
print('matched segs',nm,'kanji voted',len(res))
pickle.dump(dict(V),open('votes.pkl','wb'))
