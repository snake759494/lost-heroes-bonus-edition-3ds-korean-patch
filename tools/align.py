# Align font cells (SJIS-sorted) to JIS chars by monotonic DP
import numpy as np,sys
from PIL import Image,ImageDraw,ImageFont
name,cw,chh,N,out=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),sys.argv[5]
a=np.array(Image.open(name)).astype(np.float32)/255;nt=a.shape[1]//256
cells=[a[r*chh:(r+1)*chh,t*256+c*cw:t*256+(c+1)*cw] for t in range(nt) for r in range(512//chh) for c in range(256//cw)][:N]
cands=[]
for b1 in list(range(0x81,0xa0))+list(range(0xe0,0xf0)):
    for b2 in range(0x40,0xfd):
        if b2==0x7f: continue
        try: ch=bytes([b1,b2]).decode('cp932')
        except: continue
        if ch not in cands: cands.append(ch)
R=20
def norm(g):
    ys,xs=np.nonzero(g>0.35)
    if len(ys)==0: return None,None
    y0,y1,x0,x1=ys.min(),ys.max()+1,xs.min(),xs.max()+1
    v=np.array(Image.fromarray((g[y0:y1,x0:x1]*255).astype(np.uint8)).resize((R,R),Image.BILINEAR),np.float32).ravel()
    v=v-v.mean();v/=max(np.linalg.norm(v),1e-6)
    return v,(y1-y0,x1-x0)
fonts=[ImageFont.truetype('C:/Windows/Fonts/'+f,sz) for f,sz in [('msgothic.ttc',chh-2),('meiryo.ttc',chh-3),('YuGothM.ttc',chh-2)]]
KV=[];KI=[]
for ch in cands:
    vs=[];ii=[]
    for f in fonts:
        im=Image.new('L',(48,48));ImageDraw.Draw(im).text((8,8),ch,fill=255,font=f)
        v,i=norm(np.array(im,np.float32)/255)
        if v is None: v=np.zeros(R*R,np.float32);i=(0,0)
        vs.append(v);ii.append(i)
    KV.append(vs);KI.append(ii)
KV=np.array(KV);KI=np.array(KI,np.float32)  # K x F x D
CV=[];CI=[]
for g in cells:
    v,i=norm(g)
    if v is None: v=np.zeros(R*R,np.float32);i=(0,0)
    CV.append(v);CI.append(i)
CV=np.array(CV);CI=np.array(CI,np.float32)
S=np.einsum('nd,kfd->nkf',CV,KV)
sz=np.abs(CI[:,None,None,:]-KI[None,:,:,:]).sum(-1)
S=(S-0.02*sz).max(-1)  # N x K
# blank cell (index0 = space)
n,K=S.shape
# DP: choose strictly increasing k for each cell maximize sum S
D=np.full((n,K),-1e9,np.float32);P=np.zeros((n,K),np.int32)
D[0]=S[0]
for i in range(1,n):
    pm=np.maximum.accumulate(np.concatenate([[-1e9],D[i-1][:-1]]))
    arg=np.zeros(K,np.int32);best=-1e9;bi=0
    prev=D[i-1]
    # running argmax of prev[:k]
    am=np.zeros(K,np.int32);cur=-1e18;ci=0
    for k in range(K):
        am[k]=ci
        if prev[k]>cur: cur=prev[k];ci=k
    D[i]=pm+S[i];P[i]=am
k=int(D[-1].argmax());res=[0]*n
for i in range(n-1,-1,-1):
    res[i]=k;k=P[i][k]
s=''.join(cands[k] for k in res)
sc=S[np.arange(n),res]
open(out,'w',encoding='utf-8').write(s)
np.save(out+'.npy',sc)
print(s[:200]);print('low',sum(sc<0.5))
