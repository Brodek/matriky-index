"""da2.py <bookid> <level> <outdir> <page|a-b> ... — DigiArchiv SOA Třeboň page images (Zoomify tiles via isrv8)."""
import io, os, re, sys, time, urllib.request, http.cookiejar
from PIL import Image
B = "https://digi.ceskearchivy.cz"
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", "Mozilla/5.0")]
def get(u, ref=None, tries=4):
    for t in range(tries):
        try:
            r = urllib.request.Request(B + u, headers={"Referer": ref} if ref else {})
            return op.open(r, timeout=60).read()
        except Exception:
            time.sleep(2 + 2 * t)
    return b""
book, level, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
os.makedirs(out, exist_ok=True)
get(f"/DA?lang=cs&menu=3&id={book}&page=1")
pages = []
for a in sys.argv[4:]:
    lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
    pages += list(range(lo, hi + 1))
for p in pages:
    fn = os.path.join(out, f"{p:04d}.jpg")
    if os.path.exists(fn): continue
    ref = f"{B}/view.php?lang=cs&menu=3&id={book}&page={p}"
    h = get(f"/view.php?lang=cs&menu=3&id={book}&page={p}").decode("utf-8", "ignore")
    m = re.search(r'showImage\("myContainer","([^"]+)"', h)
    if not m: print(p, "no image"); continue
    iid = m.group(1)
    tiles = {}
    r = 0
    while True:
        c = 0
        while True:
            d = get(f"/cgi-bin/isrv8.cgi?{iid}.0.{level}-{c}-{r}", ref)
            try: im = Image.open(io.BytesIO(d)); im.load()
            except Exception: break
            tiles[(c, r)] = im; c += 1
        if c == 0: break
        r += 1
    if not tiles: print(p, "no tiles"); continue
    T = tiles[(0, 0)].width
    cols = max(k[0] for k in tiles) + 1; rows = max(k[1] for k in tiles) + 1
    W = sum(tiles[(c, 0)].width for c in range(cols)); H = sum(tiles[(0, r)].height for r in range(rows))
    G = Image.new("RGB", (W, H), "white")
    for (c, r), im in tiles.items(): G.paste(im, (c * T, r * T))
    G.save(fn, quality=88); print(p, G.size)
