import json,sys
M=json.load(open('rectmeta.json'));A=json.load(open('all_rect.json',encoding='utf-8'))
sys.stdout=open('o.txt','w',encoding='utf-8')
for p in sys.argv[1:]:
    print('@'+p)
    for n in sorted(k for k in A if k.startswith(p)):
        h,k,x,y,w,hh,e=M[n];print(' %d (%d,%d,%d,%d) %s'%(k,x,y,w,hh,A[n]))
