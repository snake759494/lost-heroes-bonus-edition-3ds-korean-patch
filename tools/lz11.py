import struct
def dec(d,o=0):
    assert d[o]==0x11
    n=d[o+1]|d[o+2]<<8|d[o+3]<<16;p=o+4
    if n==0: n=struct.unpack_from('<I',d,p)[0];p+=4
    out=bytearray()
    while len(out)<n:
        f=d[p];p+=1
        for i in range(8):
            if len(out)>=n: break
            if f&(0x80>>i)==0: out.append(d[p]);p+=1;continue
            b=d[p];t=b>>4
            if t==0: L=(((b&15)<<4)|(d[p+1]>>4))+0x11;D=(((d[p+1]&15)<<8)|d[p+2])+1;p+=3
            elif t==1: L=(((b&15)<<12)|(d[p+1]<<4)|(d[p+2]>>4))+0x111;D=(((d[p+2]&15)<<8)|d[p+3])+1;p+=4
            else: L=t+1;D=(((b&15)<<8)|d[p+1])+1;p+=2
            for _ in range(L): out.append(out[-D])
    return bytes(out)
def enc_raw(data):
    # no compression: all literals
    n=len(data);h=bytearray([0x11])
    if n<0x1000000: h+=bytes([n&255,n>>8&255,n>>16])
    else: h+=b'\0\0\0'+struct.pack('<I',n)
    out=bytearray(h)
    for i in range(0,n,8):
        out.append(0);out+=data[i:i+8]
    return bytes(out)
def comp_dec(d):
    assert d[:4]==b'COMP';return dec(d,4)
def comp_enc(data): return b'COMP'+enc_raw(data)
