import json,sys,numpy as np
from PIL import Image,ImageDraw
I=json.load(open('texidx.json'))
p=sys.argv[1];x0,y0,x1,y1=map(int,sys.argv[2].split(','));s=int(sys.argv[3]) if len(sys.argv)>3 else 6
h=[k for k in I if k.startswith(p)][0];a=np.array(Image.open((sys.argv[4] if len(sys.argv)>4 else 'texdump')+'/%s.png'%h).convert('RGBA')).astype(float)
a=a[y0:y1,x0:x1];al=a[...,3:4]/255;c=(a[...,:3]*al+60*(1-al)).astype(np.uint8)
im=Image.fromarray(c).resize(((x1-x0)*s,(y1-y0)*s),Image.NEAREST);d=ImageDraw.Draw(im)
for y in range(y0,y1):
    if y%5==0: d.line([(0,(y-y0)*s),(8 if y%10 else 20,(y-y0)*s)],fill=(255,0,0));
for x in range(x0,x1):
    if x%5==0: d.line([((x-x0)*s,0),((x-x0)*s,8 if x%10 else 20)],fill=(255,0,0))
im.save('zc.png')
