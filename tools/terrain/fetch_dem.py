import math, sys, urllib.request, os
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
z = 12
def tile(lat, lon):
    n = 2**z
    x = (lon + 180) / 360 * n
    lr = math.radians(lat)
    y = (1 - math.log(math.tan(lr) + 1/math.cos(lr)) / math.pi) / 2 * n
    return x, y
cx, cy = tile(46.53, 11.78)
print("centre tile", cx, cy)
x0, y0 = int(cx) - 1, int(cy) - 1
for dy in range(3):
    for dx in range(3):
        x, y = x0 + dx, y0 + dy
        url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
        p = os.path.join(out, f"{z}_{x}_{y}.png")
        urllib.request.urlretrieve(url, p)
        print(url, os.path.getsize(p))
