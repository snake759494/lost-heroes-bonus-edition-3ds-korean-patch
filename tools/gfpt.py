import struct,sys,os
sys.path.insert(0,os.path.dirname(__file__))
import tex
def textures(d):
    ho=d.find(b'CTPK');c=d[ho:]
    n=struct.unpack_from('<H',c,6)[0];do=struct.unpack_from('<I',c,8)[0]
    out=[]
    for i in range(n):
        e=struct.unpack_from('<IIIIHH',c,0x20+i*0x20)
        w,h=e[4],e[5];dsz=e[1];off=e[2]
        out.append(dict(w=w,h=h,fmt=e[3],pos=ho+do+off,size=dsz))
    return out
