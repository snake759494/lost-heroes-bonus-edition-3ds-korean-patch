import struct


class BR:
    def __init__(s, b, p):
        s.b = b; s.p = p; s.n = 0; s.last = 0

    def pop(s):
        if s.n % 8 == 0:
            s.last = s.b[s.p] << 24; s.p += 1
        else:
            s.last = (s.last << 1) & 0xffffffff
        s.n += 1
        return (s.last >> 31) & 1

    def int(s, n):
        v = 0
        for _ in range(n):
            v = v * 2 + s.pop()
        return v

    def length(s):
        n = 1
        while s.pop() == 0:
            n += 1
        return n


def var(b, p):
    v = 0
    for k in range(4):
        d = b[p]; p += 1
        if k == 3:
            return (v << 8) | d, p
        if not d & 0x80:
            return ((v << 7) | d) if k else d, p
        v = (v << 7) | (d & 0x7f)


def parse(b):
    """Return list of segments. Each segment: dict(kind='sync'|'sub', pos, raw_header, flags, extra, chunks=[(sid, einfo, hdrbytes, data)], end)."""
    p = 0; segs = []; size = 0; sync_pos = 0
    while p < len(b):
        seg = {}
        if b[p:p + 2] == b'L2':
            sync_pos = p
            size = struct.unpack_from('>H', b, p + 12)[0] + 1
            q = p + 14
            while True:
                t, q = var(b, q); ss, q = var(b, q)
                if t == 0:
                    q += ss; break
                q += ss
            seg['kind'] = 'sync'; seg['header'] = b[p:q]
        else:
            if all(x == 0 for x in b[p:p + 16]):
                break
            q = p; seg['kind'] = 'sub'; seg['header'] = b''
        seg['pos'] = p
        flags = b[q]; q += 1; extra = b''
        if flags & 2:
            extra = b[q:q + 2]; q += 2
        chunks = []
        limit = p + size
        while q < limit and q < len(b) and b[q] != 0:
            br = BR(b, q); bits = br.length(); sid = br.int(bits); end = br.pop(); einfo = None
            if end:
                b1 = br.length(); v1 = br.int(b1); f = br.pop(); b2 = br.length(); v2 = br.int(b2 * 2 + 26)
                einfo = (b1, v1, f, b2, v2)
            psz = br.int(13) + 1; hq = q; q = br.p
            chunks.append((sid, einfo, b[hq:q], b[q:q + psz])); q += psz
        seg.update(flags=flags, extra=extra, chunks=chunks)
        if flags % 2 == 0:
            seg['end'] = p + size; p = p + size
        else:
            if q < limit and q < len(b) and b[q] == 0:
                q += 1  # terminator
                seg['term'] = True
            else:
                seg['term'] = False
            seg['end'] = q; p = q
        segs.append(seg)
    return segs


def frames(segs):
    out = []; cur = {}
    for s in segs:
        for sid, e, h, d in s['chunks']:
            cur.setdefault(sid, []).append(d)
            if e:
                out.append((sid, e, b''.join(cur[sid]))); cur[sid] = []
    return out
