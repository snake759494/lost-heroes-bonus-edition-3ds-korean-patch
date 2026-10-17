import struct
CFMT = ['rgba8', 'rgb8', 'rgba5551', 'rgb565', 'rgba4', 'la8', 'hilo8', 'l8', 'a8', 'la4', 'l4', 'a4', 'etc1', 'etc1a4']
def textures(d):
    """return list of dict(name,fmt,w,h,pos,size) for CTPK inside d (GFPT or raw)"""
    ho = d.find(b'CTPK')
    if ho < 0: return []
    c = d[ho:]
    n = struct.unpack_from('<H', c, 6)[0]
    do = struct.unpack_from('<I', c, 8)[0]
    out = []
    for i in range(n):
        noff, sz, off, fmt, w, h = struct.unpack_from('<IIIIHH', c, 0x20 + i * 0x20)
        name = c[noff:c.index(b'\0', noff)].decode('latin1') if 0 < noff < len(c) else str(i)
        out.append(dict(name=name, fmt=CFMT[fmt] if fmt < len(CFMT) else str(fmt), w=w, h=h, pos=ho + do + off, size=sz))
    return out
