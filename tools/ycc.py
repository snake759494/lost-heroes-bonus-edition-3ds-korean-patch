import numpy as np
W,H=400,240
def load(i,d='yuv'):
    b=np.fromfile('%s/%05d.yuv'%(d,i),np.uint8).astype(float)
    Y=b[:W*H].reshape(H,W);U=b[W*H:W*H+W*H//4].reshape(H//2,W//2);V=b[W*H+W*H//4:].reshape(H//2,W//2)
    return Y,U,V
def to_rgb(Y,U,V):
    cg=U.repeat(2,0).repeat(2,1)-128;co=V.repeat(2,0).repeat(2,1)-128
    return np.clip(np.stack([Y-cg+co,Y+cg,Y-cg-co],-1),0,255).astype(np.uint8)
def from_rgb(rgb):
    r,g,b=[rgb[...,k].astype(float) for k in range(3)]
    Y=(r+2*g+b)/4;cg=(-r+2*g-b)/4;co=(r-b)/2
    sub=lambda x:x.reshape(H//2,2,W//2,2).mean((1,3))
    return Y,sub(cg)+128,sub(co)+128
def save(Y,U,V,f):
    np.concatenate([np.clip(np.round(x),0,255).astype(np.uint8).ravel() for x in (Y,U,V)]).tofile(f)
