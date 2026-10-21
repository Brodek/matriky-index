"""Download a zayt.org page (Zoomify, /partial/ tiles) and stitch it.
usage: python -I zayt.py <book_base_url e.g. https://files.zayt.org/zayt-239/books/235/> <page> <outdir> [level_offset] [x0 y0 x1 y1 fractions]
level_offset: 0 = top level (full res), 1 = half, ...
"""
import sys, re, math, io, os, concurrent.futures as cf
import requests
from PIL import Image

base, page, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
off = int(sys.argv[4]) if len(sys.argv) > 4 else 0
crop = [float(v) for v in sys.argv[5:9]] if len(sys.argv) > 8 else None
if not base.endswith('/'):
    base += '/'
pu = f"{base}p{page}/"
H = {"Referer": "https://zayt.org/", "User-Agent": "Mozilla/5.0"}
xml = requests.get(pu + "ImageProperties.xml", headers=H, timeout=30).text
W = int(re.search(r'WIDTH="(\d+)"', xml).group(1)); Hh = int(re.search(r'HEIGHT="(\d+)"', xml).group(1))
TS = int(re.search(r'TILESIZE="(\d+)"', xml).group(1)); NT = int(re.search(r'NUMTILES="(\d+)"', xml).group(1))

def tiers_trunc():
    t = []; ts = TS
    while W > ts or Hh > ts:
        t.append((math.ceil(W / ts), math.ceil(Hh / ts))); ts += ts
    t.append((1, 1)); t.reverse(); return t

def tiers_def():
    t = []; w, h = W, Hh
    while w > TS or h > TS:
        t.append((math.ceil(w / TS), math.ceil(h / TS))); w >>= 1; h >>= 1
    t.append((1, 1)); t.reverse(); return t

tiers = tiers_trunc()
if sum(a * b for a, b in tiers) != NT:
    tiers = tiers_def()
assert sum(a * b for a, b in tiers) == NT, (tiers, NT)
z = len(tiers) - 1 - off
nx, ny = tiers[z]
before = sum(a * b for a, b in tiers[:z])
scale = 2 ** off
lw, lh = math.ceil(W / scale), math.ceil(Hh / scale)
xs = range(nx); ys = range(ny)
if crop:
    x0, y0, x1, y1 = crop
    xs = range(int(x0 * lw) // TS, min(nx, int(math.ceil(x1 * lw / TS))))
    ys = range(int(y0 * lh) // TS, min(ny, int(math.ceil(y1 * lh / TS))))
pp = pu.replace("https://files.zayt.org/", "https://files.zayt.org/partial/")

def fetch(xy):
    x, y = xy
    idx = before + y * nx + x
    u = f"{pp}TileGroup{idx // 256}/{z}-{x}-{y}.jpg"
    r = requests.get(u, headers=H, timeout=60)
    if r.status_code != 200:
        return xy, None
    return xy, Image.open(io.BytesIO(r.content)).convert("RGB")

img = Image.new("RGB", (len(xs) * TS, len(ys) * TS), "white")
miss = 0
with cf.ThreadPoolExecutor(8) as ex:
    for (x, y), t in ex.map(fetch, [(x, y) for y in ys for x in xs]):
        if t is None:
            miss += 1; continue
        img.paste(t, ((x - xs.start) * TS, (y - ys.start) * TS))
os.makedirs(outdir, exist_ok=True)
name = base.rstrip('/').split('/')[-1]
fn = os.path.join(outdir, f"{name}_p{page}_o{off}" + ("_c" if crop else "") + ".jpg")
img.save(fn, quality=90)
print(fn, img.size, "full", W, Hh, "level", z, "tiles", nx, ny, "missing", miss)
