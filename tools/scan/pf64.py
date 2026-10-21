"""pf64.py <book> <outdir> <width> <a-b|n> ... — Porta fontium vs-horazdovice amtsbuch (soap-pn_20033-vs-horazdovice_kNNNN_XXXX)."""
import os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
book, out, wid = sys.argv[1], sys.argv[2], int(sys.argv[3])
os.makedirs(out, exist_ok=True)
ks = []
for a in sys.argv[4:]:
    lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
    ks += range(lo, hi + 1)
def one(k):
    f = os.path.join(out, f"{k:04d}.jpg")
    if not os.path.exists(f):
        u = (f"https://www.portafontium.eu/fcgi-bin/iipsrv.fcgi?FIF=amtsbuch/soap-pn/vs-horazdovice/{book}/"
             f"soap-pn_20033-vs-horazdovice_{book}_{k*10:04d}.jp2&WID={wid}&CVT=jpeg")
        data = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
        open(f, "wb").write(data)
    return k
with ThreadPoolExecutor(6) as ex:
    print(len(list(ex.map(one, ks))))
