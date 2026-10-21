"""ebget.py <matrikaId> <Name_NN> <outdir> <n|a-b> ... — stáhne skeny z eBadatelny SOA Praha a uloží náhledy _s.jpg."""
import http.cookiejar
import os
import sys
import urllib.request

from PIL import Image

mid, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", "Mozilla/5.0")]
os.makedirs(out, exist_ok=True)
for a in sys.argv[4:]:
    lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
    for k in range(lo, hi + 1):
        p = os.path.join(out, f"{k:04d}.jpg")
        if not os.path.exists(p):
            op.open(f"https://ebadatelna.soapraha.cz/d/{mid}/{k}", timeout=60).read()
            data = op.open(f"https://ebadatelna.soapraha.cz/wicket/resource/org.apache.wicket.Application/{name}__{k:03d}.jpg",
                           timeout=120).read()
            if data[:2] != b"\xff\xd8":
                print(k, "not an image")
                continue
            open(p, "wb").write(data)
        im = Image.open(p)
        im.resize((1600, int(1600 * im.size[1] / im.size[0]))).save(os.path.join(out, f"{k:04d}_s.jpg"), quality=85)
        print(k, im.size)
