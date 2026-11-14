"""pfl.py <book> <outdir> <width> <a-b|n> ... — Porta fontium images by snímek, the scan's position in the portal viewer
(1, 2, 3 …; the same number as in the index, Mapa matrik and the rodokmen skill), read from the book's page.
Saves <outdir>/<NNNN><suffix>.jpg, NNNN = snímek, suffix = that of the image file (-n, -o, -z, -x …).

<book> is a register book (dolni-bela-17) or a full book address (amtsbuch, urbar)."""
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slusne  # noqa: E402

book, out, wid = sys.argv[1], sys.argv[2], int(sys.argv[3])
url = book if "://" in book else f"https://www.portafontium.eu/register/soap-pn/{book}"
os.makedirs(out, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}


def get(u):
    druh = "obrazek" if "iipsrv" in u else "stranka"
    return slusne.urlopen(urllib.request.Request(u, headers=UA), druh, timeout=120).read()


page = get(url).decode("utf-8", "replace")
paths = list(dict.fromkeys(re.findall(r'data-iip-path="([^"]+)"', page)))
ks = []
for a in sys.argv[4:]:
    lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
    ks += [k for k in range(lo, hi + 1) if 1 <= k <= len(paths)]


def one(k):
    path = paths[k - 1]
    m = re.search(r"\d{4}(-[a-z]+)?\.jp2$", path)
    suf = m[1] if m and m[1] else ""
    p = os.path.join(out, f"{k:04d}{suf}.jpg")
    if not os.path.exists(p):
        u = f"https://www.portafontium.eu/fcgi-bin/iipsrv.fcgi?FIF={path.lstrip('/')}&WID={wid}&CVT=jpeg"
        open(p, "wb").write(get(u))
    return f"{k}{suf}"


with ThreadPoolExecutor(6) as ex:
    print(" ".join(ex.map(one, ks)))
