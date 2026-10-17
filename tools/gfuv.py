import struct
def blocks(d):
    """yield (texname, [(x,y,w,h),...]) for every GFUV block in a GTSF blob"""
    p = 0
    while True:
        i = d.find(b'GFUV', p)
        if i < 0: return
        sz, ver, cnt = struct.unpack_from('<I4sI', d, i + 4)
        name = d[i + 0x10:i + 0x34].split(b'\0')[0].decode('latin1')
        rects = [struct.unpack_from('<4H', d, i + 0x34 + k * 8) for k in range(cnt)]
        yield name, rects
        p = i + 4
