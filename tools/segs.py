import sys,glob,os;sys.path.insert(0,os.path.dirname(__file__))
from mbb import parse
def segments(maxg=2112):
    segs=set()
    for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__),'..','ext/romfs/**/*.mbb'),recursive=True)):
        for k,t in parse(open(f,'rb').read()):
            if k!='MTBL': continue
            for s in t:
                if not s: continue
                cur=[]
                for v in s+[0xffff]:
                    if 1<=v<=maxg: cur.append(v-1)
                    else:
                        if len(cur)>=2: segs.add(tuple(cur))
                        cur=[]
    return sorted(segs)
