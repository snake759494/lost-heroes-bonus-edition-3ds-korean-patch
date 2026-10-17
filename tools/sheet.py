import pickle,numpy as np,sys
from PIL import Image,ImageDraw,ImageFont
res,unsure=pickle.load(open('comb.pkl','rb'));cands,S=pickle.load(open('tmpl.pkl','rb'))
V=pickle.load(open('votes.pkl','rb'))
a=np.array(Image.open('Font14.png'))
cells=[a[r*16:(r+1)*16,t*256+c*14:t*256+(c+1)*14] for t in range(4) for r in range(32) for c in range(18)]
f=ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc',22);fs=ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc',12)
lst=[int(x) for x in sys.argv[2].split(',')] if len(sys.argv)>2 else unsure
per=60
for p in range(0,len(lst),per):
    im=Image.new('RGB',(10*190,6*70),'white');d=ImageDraw.Draw(im)
    for k,g in enumerate(lst[p:p+per]):
        x=(k%10)*190;y=(k//10)*70
        gl=Image.fromarray(255-cells[g]).resize((42,48),Image.NEAREST);im.paste(gl,(x+2,y+2))
        top=[cands[i] for i in np.argsort(-S[g-363])[:4]]
        vc=V.get(g);vs=''.join(c for c,_ in vc.most_common(2)) if vc else ''
        d.text((x+48,y),''.join(top),font=f,fill='black')
        d.text((x+48,y+34),'%d v:%s'%(g,vs),font=fs,fill='blue')
    im.save('%s%d.png'%(sys.argv[1],p//per))
