import os
T=open(os.path.join(os.path.dirname(__file__),'..','jtab.txt'),encoding='utf-8').read()
def dec(a):
    o=[]
    for v in a:
        if v==0x8001: o.append('\n')
        elif 1<=v<=len(T): o.append(T[v-1])
        else: o.append('{%x}'%v)
    return ''.join(o)
