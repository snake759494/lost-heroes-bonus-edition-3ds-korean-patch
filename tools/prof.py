import json,sys,numpy as np
from PIL import Image
I=json.load(open('texidx.json'))
p=sys.argv[1];x0,y0,x1,y1=map(int,sys.argv[2].split(','));th=int(sys.argv[3]) if len(sys.argv)>3 else 170
h=[k for k in I if k.startswith(p)][0];a=np.array(Image.open('texdump/%s.png'%h).convert('RGBA')).astype(int)
L=a[...,:3].mean(-1)*(a[...,3]>100);m=L[y0:y1,x0:x1]>th
r=m.sum(1);runs=[];cur=None
for i,v in enumerate(r):
    if v and cur is None: cur=i
    if not v and cur is not None: runs.append((y0+cur,y0+i));cur=None
if cur is not None: runs.append((y0+cur,y1))
for a_,b_ in runs:
    c=m[a_-y0:b_-y0].sum(0);xs=np.nonzero(c)[0];print('y',a_,b_,'x',x0+xs.min(),x0+xs.max()+1)
