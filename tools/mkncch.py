# Rebuild decrypted NCCH with replaced RomFS files; usage: mkncch.py in.ncch replace_dir out.ncch
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from build import build_romfs, al
MU = 0x200
src, rdir, outp = sys.argv[1:4]
flt = set(open(sys.argv[4], encoding='utf-8').read().split()) if len(sys.argv) > 4 else None
repl = {}
for root, _, files in os.walk(rdir):
    for fn in files:
        p = os.path.join(root, fn)
        r = os.path.relpath(p, rdir).replace(os.sep, '/')
        if flt is None or r in flt: repl[r] = open(p, 'rb').read()
f = open(src, 'rb')
h = bytearray(f.read(0x200))
assert h[0x100:0x104] == b'NCCH'
g = lambda o: struct.unpack_from('<I', h, o)[0] * MU
rfo = g(0x1b0)
tmp = open(outp + '.romfs', 'w+b')
build_romfs(f, rfo, repl, tmp); tmp.flush(); rlen = tmp.tell()
f.seek(0); pre = bytearray(f.read(rfo))
pre[0x18b] = 0; pre[0x18f] |= 4
struct.pack_into('<I', pre, 0x1b4, al(rlen, MU) // MU)
tmp.seek(0); sb = tmp.read(0x200)
hashsz = struct.unpack_from('<I', pre, 0x1b8)[0] * MU
tmp.seek(0); pre[0x1e0:0x200] = hashlib.sha256(tmp.read(hashsz)).digest()
size = al(rfo + rlen, MU)
struct.pack_into('<I', pre, 0x104, size // MU)
out = open(outp, 'wb'); out.write(pre); tmp.seek(0)
while True:
    c = tmp.read(1 << 24)
    if not c: break
    out.write(c)
out.write(b'\0' * (size - rfo - rlen)); out.close(); tmp.close(); os.remove(outp + '.romfs')
print('replaced', len(repl), 'romfs', rlen)
