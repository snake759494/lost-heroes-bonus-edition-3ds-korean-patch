import struct
def al(x, a=16): return (x + a - 1) // a * a
def parse_full(d):
    assert d[:4] == b'TBB1'
    hdr = d[:0x10]
    n = struct.unpack_from('<I', d, 8)[0]
    offs = struct.unpack_from('<%dI' % n, d, 0x10)
    tabs = []
    for o in offs:
        if d[o:o + 4] != b'MTBL':
            # raw: length up to next table / end
            nxt = min([x for x in offs if x > o] + [len(d)])
            tabs.append(['RAW', d[o:nxt]]); continue
        unk, sz, cnt = struct.unpack_from('<III', d, o + 4)
        so = struct.unpack_from('<%dI' % (cnt + 1), d, o + 0x10)
        strs = []
        for k, s in enumerate(so):
            if s == 0 or s >= sz:
                strs.append(None); continue
            if s % 16:
                strs.append(('OFF', s)); continue
            p = o + 0x10 + s; a = []
            while True:
                v = struct.unpack_from('<H', d, p)[0]; p += 2
                if v == 0: break
                a.append(v)
            strs.append(a)
        tabs.append(['MTBL', strs, unk])
    return hdr, tabs
def build(hdr, tabs):
    blobs = []
    for t in tabs:
        if t[0] == 'RAW': blobs.append(t[1]); continue
        strs = t[1]; cnt = len(strs) - 1
        body = bytearray(); offs = []
        base = al((cnt + 1) * 4)
        for s in strs:
            if s is None: offs.append(0); continue
            if isinstance(s, tuple): offs.append(s[1]); continue
            offs.append(base + len(body))
            body += struct.pack('<%dH' % (len(s) + 1), *(list(s) + [0]))
            body += b'\0' * (al(len(body)) - len(body))
        tbl = bytearray(struct.pack('<4sIII', b'MTBL', t[2], 0, cnt))
        tbl += struct.pack('<%dI' % (cnt + 1), *offs); tbl += b'\0' * (0x10 + base - len(tbl))
        tbl += body
        struct.pack_into('<I', tbl, 8, len(tbl) - 0x10)
        blobs.append(bytes(tbl))
    n = len(tabs)
    out = bytearray(hdr)
    out += b'\0' * (al(0x10 + 4 * n) - len(out))
    offs = []
    for b in blobs:
        out += b'\0' * (al(len(out)) - len(out))
        offs.append(len(out)); out += b
    out += b'\0' * (al(len(out)) - len(out))
    struct.pack_into('<%dI' % n, out, 0x10, *offs)
    struct.pack_into('<I', out, 12, len(out))
    return bytes(out)
