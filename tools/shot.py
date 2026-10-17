import ctypes
import sys,os,time,glob,shutil
sys.path.insert(0,os.path.dirname(__file__))
from emu import *
from ctrlkey import ctrl_key
B=os.path.join(os.path.dirname(__file__),'..')
pid=int(open(os.path.join(B,'emu.pid')).read())
import ctypes.wintypes as W2
allw=[]
@ctypes.WINFUNCTYPE(W2.BOOL,W2.HWND,W2.LPARAM)
def _cb(hh,l):
    if u.IsWindowVisible(hh) and title(hh).startswith('Azahar') and hh in wins(pid): allw.append(hh)
    return True
u.EnumWindows(_cb,0)
h=allw[0]
for s in sys.argv[2:]:
    if s.startswith('w'): time.sleep(float(s[1:]));continue
    k,_,n=s.partition('*')
    for i in range(int(n or 1)): key(h,k);time.sleep(0.35)
old=set(glob.glob(os.path.join(B,'shots','*.png')))
new=set()
for att in range(4):
    ctrl_key(h,ord('P'))
    for i in range(40):
        time.sleep(0.25);new=set(glob.glob(os.path.join(B,'shots','*.png')))-old
        if new: break
    if new: break
f=list(new)[0];time.sleep(0.3);shutil.move(f,sys.argv[1]);print('saved',sys.argv[1])
