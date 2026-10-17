import struct
def parse(d):
    assert d[:4]==b'TBB1'
    n,size=struct.unpack_from('<II',d,8)
    offs=struct.unpack_from('<%dI'%n,d,0x10)
    tabs=[]
    for o in offs:
        mg=d[o:o+4]
        if mg!=b'MTBL': tabs.append(('RAW',d[o:o+struct.unpack_from('<I',d,o+8)[0]]));continue
        sz,cnt=struct.unpack_from('<II',d,o+8)
        so=struct.unpack_from('<%dI'%cnt,d,o+0x10)
        strs=[]
        for k,s in enumerate(so):
            if (s==0 and k>0) or s>=sz: strs.append(None);continue
            p=o+0x10+s;a=[]
            while True:
                v=struct.unpack_from('<H',d,p)[0];p+=2
                if v==0: break
                a.append(v)
            strs.append(a)
        tabs.append(('MTBL',strs))
    return tabs
