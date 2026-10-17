import struct
def parse(b):
    assert b[:4] == b'2NBF'
    n, base, al = struct.unpack_from('<III', b, 4)
    ents = []
    for i in range(n):
        o = 0x10 + i * 0x8c
        name = b[o:o + 0x80].split(b'\0')[0].decode('ascii')
        off, unk, sz = struct.unpack_from('<III', b, o + 0x80)
        ents.append([name, unk, b[base + off:base + off + sz]])
    return (n, base, al), ents, b
def build(hdr, ents, orig=None):
    n, base, al = hdr
    out = bytearray(orig[:base]) if orig is not None else bytearray(base)
    struct.pack_into('<4sIII', out, 0, b'2NBF', len(ents), base, al)
    data = bytearray()
    for i, (name, unk, d) in enumerate(ents):
        o = 0x10 + i * 0x8c
        nm = name.encode('ascii'); out[o:o + 0x80] = nm + b'\0' * (0x80 - len(nm))
        struct.pack_into('<III', out, o + 0x80, len(data), unk, len(d))
        data += d
        data += b'\0' * ((-len(data)) % al)
    return bytes(out + data)
