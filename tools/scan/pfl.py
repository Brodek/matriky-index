"""pfl.py <book> <outdir> <width> <a-b|n> ... — Porta fontium register images by snímek number (NNNN/10),
any suffix (-n, -o, -z, -x ...), file names read from the book's page. Saves <outdir>/<NNNN><suffix>.jpg."""
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slusne  # noqa: E402

book, out, wid = sys.argv[1], sys.argv[2], int(sys.argv[3])
parish = book.rsplit("-", 1)[0]
os.makedirs(out, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}


def get(u):
    druh = "obrazek" if "iipsrv" in u else "stranka"
    return slusne.urlopen(urllib.request.Request(u, headers=UA), druh, timeout=120).read()


page = get(f"https://www.portafontium.eu/register/soap-pn/{book}").decode("utf-8", "replace")
found = re.findall(rf"{book}/({book}_(\d{{4}})(-[a-z]+)?\.jp2)", page)
div = 10 if all(int(n[1]) % 10 == 0 for n in found) else 1
names = {int(n[1]) // div: (n[0], n[2]) for n in found}
ks = []
for a in sys.argv[4:]:
    lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
    ks += [k for k in range(lo, hi + 1) if k in names]


def one(k):
    fn, suf = names[k]
    p = os.path.join(out, f"{k:04d}{suf}.jpg")
    if not os.path.exists(p):
        u = f"https://www.portafontium.eu/fcgi-bin/iipsrv.fcgi?FIF=register/soap-pn/{parish}/{book}/{fn}&WID={wid}&CVT=jpeg"
        open(p, "wb").write(get(u))
    return f"{k}{suf}"


with ThreadPoolExecutor(6) as ex:
    print(" ".join(ex.map(one, ks)))
