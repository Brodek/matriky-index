"""zget.py <code> <sign> <outdir> <n|a-b> ... — stáhne snímky z matriky SOA Zámrsk a uloží i zmenšené náhledy _s.jpg."""
import io
import os
import sys
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from rzip import RangeFile  # noqa: E402

code, sign, out = sys.argv[1], sys.argv[2], sys.argv[3]
url = f"https://storage.vychodoceskearchivy.cz/matriky/{code[0]}/CZ_215000010_00190_{code}_sign-{sign}.zip"
z = zipfile.ZipFile(io.BufferedReader(RangeFile(url), buffer_size=1 << 16))
names = sorted(z.namelist())
os.makedirs(out, exist_ok=True)
if sys.argv[4:] == ["count"]:
    print(len(names))
    sys.exit()
for a in sys.argv[4:]:
    lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
    for k in range(lo, hi + 1):
        p = os.path.join(out, f"{k:04d}.jpg")
        if not os.path.exists(p):
            with open(p, "wb") as f:
                f.write(z.read(names[k - 1]))
        im = Image.open(p)
        w = 1600
        im.resize((w, int(w * im.size[1] / im.size[0]))).save(os.path.join(out, f"{k:04d}_s.jpg"), quality=85)
        print(k, names[k - 1], im.size)
