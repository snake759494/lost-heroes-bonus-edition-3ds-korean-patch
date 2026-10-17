import re
TOK = re.compile(r'(⟦[0-9a-f]{4}(?::\d+)?⟧)')
HALF = {}
def _init():
    # ascii ink widths approximated from NanumSquare-like/original half-width cells
    import json, os
    p = os.path.join(os.path.dirname(__file__), '..', 'asciiw.json')
    if os.path.exists(p): HALF.update(json.load(open(p)))
_init()
def cw(c):
    if c == ' ': return 5
    if c in HALF: return HALF[c]
    if ord(c) < 0x80: return 8
    return 14
def tw(t):
    m = re.fullmatch(r'⟦([0-9a-f]{4})(?::(\d+))?⟧', t)
    if m: return 14 * int(m.group(2) or 0)
    return sum(cw(c) for c in t)
def width(line):
    return sum(tw(p) for p in TOK.split(line) if p)
def wrap_page(text, W):
    """greedy wrap a page (no ⟦8002⟧ inside) into lines <= W px; returns list of lines"""
    words = []
    for ln in text.split('\n'):
        ln = ln.strip(' ')
        if ln: words += [w for w in re.split(r'(?<= )|(?= )', ln) if w]
        words.append('\n')
    # collapse: join all, treat original newlines as spaces
    flat = ' '.join(l.strip(' ') for l in text.split('\n') if l.strip(' '))
    toks = re.split(r'( )', flat)
    lines = []; cur = ''
    for t in toks:
        if t == '':
            continue
        cand = cur + t
        if width(cand.rstrip(' ')) <= W or cur.strip() == '':
            cur = cand
        else:
            lines.append(cur.rstrip(' ')); cur = t.lstrip(' ') if t != ' ' else ''
    if cur.strip(' '): lines.append(cur.rstrip(' '))
    return lines
def rewrap(text, W, maxlines):
    pages = re.split(r'(⟦8002⟧)', text)
    out = []; ok = True
    for p in pages:
        if p == '⟦8002⟧': out.append(p); continue
        # keep original if already fits
        ls = p.split('\n')
        lead = ''
        if all(width(l) <= W for l in ls) and len([l for l in ls if l.strip()]) <= maxlines:
            out.append(p); continue
        nl = wrap_page(p, W)
        if len(nl) > maxlines or any(width(l) > W for l in nl): ok = False
        out.append('\n'.join(nl))
    return ''.join(out), ok
