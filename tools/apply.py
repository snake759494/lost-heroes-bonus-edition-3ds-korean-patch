import struct,sys
def readpk(f):
    d=open(f,'rb').read();n=struct.unpack_from('<i',d,0)[0];o=4;v=[]
    for _ in range(n):
        l=struct.unpack_from('<i',d,o)[0];o+=4;v.append(d[o:o+l]);o+=l
    return v
def readtc(f):
    d=open(f,'rb').read();n=struct.unpack_from('<i',d,0)[0];o=4;rep={}
    for _ in range(n):
        i,l=struct.unpack_from('<ii',d,o);o+=8;rep[i]=d[o:o+l];o+=l
    return rep
def writepk(f,v):
    with open(f,'wb') as o:
        o.write(struct.pack('<i',len(v)))
        for p in v: o.write(struct.pack('<i',len(p))+p)
if __name__=='__main__':
    v=readpk(sys.argv[1]);rep={}
    for t in sys.argv[3:]: rep.update(readtc(t))
    writepk(sys.argv[2],[rep.get(i,p) for i,p in enumerate(v)])
