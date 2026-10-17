import json,sys,numpy as np
from PIL import Image
I=json.load(open('texidx.json'));rows=[];W=0
for p in sys.argv[2:]:
    h=[k for k in I if k.startswith(p)][0]
    for src in ('texdump','imgout'):
        a=np.array(Image.open('%s/%s.png'%(src,h)).convert('RGBA')).astype(float)
        al=a[...,3:4]/255;rows.append((a[...,:3]*al+50*(1-al)).astype(np.uint8));W=max(W,a.shape[1])
rows=[np.pad(r,((0,4),(0,W-r.shape[1]),(0,0)),constant_values=255) for r in rows]
im=np.vstack(rows);s=max(1,min(4,1400//max(im.shape[:2])))
Image.fromarray(im).resize((im.shape[1]*s,im.shape[0]*s),Image.NEAREST).save(sys.argv[1])
