import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moflex import parse

SEG = 4096


class BW:
    def __init__(s): s.bits = []
    def put(s, v, n):
        for i in range(n - 1, -1, -1): s.bits.append((v >> i) & 1)
    def length(s, n):  # n-1 zeros then 1
        for _ in range(n - 1): s.bits.append(0)
        s.bits.append(1)
    def bytes(s):
        b = s.bits + [0] * ((-len(s.bits)) % 8)
        return bytes(int(''.join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))


def bitlen(v):
    n = 1
    while v >= (1 << n): n += 1
    return n


def chunk_header(sid, einfo, size, orig_hdr=None):
    w = BW()
    # stream id: length-coded bit count then value
    nb = max(1, bitlen(sid))
    w.length(nb); w.put(sid, nb)
    if einfo is None:
        w.put(0, 1)
    else:
        b1, v1, f, b2, v2 = einfo
        w.put(1, 1); w.length(b1); w.put(v1, b1); w.put(f, 1); w.length(b2); w.put(v2, b2 * 2 + 26)
    w.put(size - 1, 13)
    return w.bytes()


def groups(segs):
    """Split original segments into groups starting at sync segments. Each group: dict(header, flags, frames=[(sid, einfo, data)])"""
    out = []
    for s in segs:
        if s['kind'] == 'sync':
            g = dict(header=s['header'], flags=s['flags'], frames=[], cur={}); out.append(g)
        g = out[-1]
        for sid, e, h, d in s['chunks']:
            g['cur'].setdefault(sid, []).append(d)
            if e:
                g['frames'].append([sid, e, b''.join(g['cur'][sid])]); g['cur'][sid] = []
    for g in out:
        assert all(not v for v in g['cur'].values()), 'frame spans groups'
        del g['cur']
    return out


def mux(gs):
    out = bytearray(); sync_pos = []
    for g in gs:
        sync_pos.append(len(out))
        segstart = len(out)
        out += g['header']; out.append(g['flags'])
        for fi, (sid, e, data) in enumerate(g['frames']):
            if fi == 1:
                out.append(0); segstart = len(out); out.append(g['flags'])
            p = 0
            while True:
                room = SEG - (len(out) - segstart)
                rest = len(data) - p
                hend = len(chunk_header(sid, e, max(1, rest)))
                if rest + hend <= room and rest <= 8192:
                    out += chunk_header(sid, e, rest) + data[p:]; break
                hmid = 2
                take = min(room - hmid, 8192, rest - 1)
                if take <= 0:
                    out.append(0); segstart = len(out); out.append(g['flags']); continue
                out += chunk_header(sid, None, take) + data[p:p + take]; p += take
                if len(out) - segstart >= SEG:
                    segstart = len(out); out.append(g['flags'])
            if len(out) - segstart >= SEG:
                segstart = len(out); out.append(g['flags'])
        if len(out) - segstart < SEG:
            out.append(0)
    return bytes(out), sync_pos


if __name__ == '__main__':
    b = open(sys.argv[1], 'rb').read()
    gs = groups(parse(b))
    m, sp = mux(gs)
    print(len(b), len(m), m == b)
    if m != b:
        for i in range(min(len(m), len(b))):
            if m[i] != b[i]:
                print('first diff', hex(i)); break
