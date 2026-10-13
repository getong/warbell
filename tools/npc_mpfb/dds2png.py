import sys, struct, glob, os
import texture2ddecoder as t
from PIL import Image
src="C:/Users/skibi/Documents/Codex/warbell/assets/forest_pbr/"; dst=sys.argv[1]; os.makedirs(dst,exist_ok=True)
for f in sorted(glob.glob(src+"*.dds")):
    n=os.path.basename(f)[:-4]
    if not (n.startswith('s_') or n.startswith('ground_') or n.startswith('people') ): continue
    d=open(f,'rb').read()
    h,w=struct.unpack_from('<II',d,12); fourcc=d[84:88]; off=128
    fmt=None
    if fourcc==b'DX10': fmt=struct.unpack_from('<I',d,128)[0]; off=148
    layers=1
    if fourcc==b'DX10': layers=struct.unpack_from('<I',d,128+12)[0]
    if fmt in (98,99): px=t.decode_bc7(d[off:off+w*h],w,h)
    elif fmt in (71,72): px=t.decode_bc1(d[off:off+w*h//2],w,h)
    elif fmt in (77,78): px=t.decode_bc3(d[off:off+w*h],w,h)
    elif fmt in (80,81): px=t.decode_bc4(d[off:off+w*h//2],w,h)
    elif fmt in (83,84): px=t.decode_bc5(d[off:off+w*h],w,h)
    else: print("skip",n,fmt,fourcc); continue
    im=Image.frombytes('RGBA',(w,h),px,'raw','BGRA')
    im.save(dst+n+".png"); print("ok",n,w,h,fmt,layers)
