import numpy as np,pickle
from PIL import Image,ImageDraw,ImageFont
a=np.array(Image.open('Font14.png')).astype(np.float32)/255
cells=[a[r*16:(r+1)*16,t*256+c*14:t*256+(c+1)*14] for t in range(4) for r in range(32) for c in range(18)]
cands=[]
for b1 in list(range(0x88,0xa0))+list(range(0xe0,0xeb)):
    for b2 in range(0x40,0xfd):
        try: ch=bytes([b1,b2]).decode('cp932')
        except: continue
        if '\u4e00'<=ch<='\u9fff' and ch not in cands: cands.append(ch)
cands+=list('々…‥〆ヶ〇')
R=16
def norm(g):
    ys,xs=np.nonzero(g>0.35)
    if len(ys)==0: return np.zeros(R*R,np.float32)
    y0,y1,x0,x1=ys.min(),ys.max()+1,xs.min(),xs.max()+1
    v=np.array(Image.fromarray((g[y0:y1,x0:x1]*255).astype(np.uint8)).resize((R,R),Image.BILINEAR),np.float32).ravel()
    v-=v.mean();return v/max(np.linalg.norm(v),1e-6)
fonts=[ImageFont.truetype('C:/Windows/Fonts/'+f,s) for f,s in [('msgothic.ttc',14),('meiryo.ttc',13),('YuGothM.ttc',14),('msgothic.ttc',13)]]
KV=np.array([[norm(np.array((lambda im:(ImageDraw.Draw(im).text((4,2),ch,fill=255,font=f),im)[1])(Image.new('L',(24,24))),np.float32)/255) for f in fonts] for ch in cands])
CV=np.array([norm(g) for g in cells[363:2112]])
S=np.einsum('nd,kfd->nkf',CV,KV).max(-1)
pickle.dump((cands,S),open('tmpl.pkl','wb'))
print(S.shape)
