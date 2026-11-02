"""ebget.py <matrikaId> <Name_NN> <outdir> <n|a-b> ... — stáhne skeny z eBadatelny SOA Praha a uloží náhledy _s.jpg.

Obrázek se bere z prohlížeče snímku (/d/<matrikaId>/<snímek>, <img id="scanImage">); Name_NN se už nepoužívá a zůstává
jen kvůli dřívějšímu volání.
"""
import http.cookiejar
import os
import re
import sys
import urllib.request

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slusne  # noqa: E402

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
            page = slusne.urlopen(f"https://ebadatelna.soapraha.cz/d/{mid}/{k}", "stranka", timeout=60, opener=op).read()
            src = re.search(rb'id="scanImage"[^>]*src="\./([^"]+)"', page)
            if not src:
                print(k, "no scan on the page")
                continue
            img = src.group(1).decode().replace("&amp;", "&")
            data = slusne.urlopen(f"https://ebadatelna.soapraha.cz/d/{mid}/{img}", "obrazek", timeout=120, opener=op).read()
            if data[:2] != b"\xff\xd8":
                print(k, "not an image")
                continue
            open(p, "wb").write(data)
        im = Image.open(p)
        im.resize((1600, int(1600 * im.size[1] / im.size[0]))).save(os.path.join(out, f"{k:04d}_s.jpg"), quality=85)
        print(k, im.size)
