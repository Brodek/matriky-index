"""Celá matrika VČA (SOA Zámrsk) pro PERO: python -I vcakniha.py <kód> <sign> <outdir> <prefix> [sirka] [kvalita] [n/procesů]

Čte zip knihy po částech (rzip.py) a ukládá zmenšené šedotónové JPEG <prefix>_NNNN.jpg (výchozí šířka 2400 px,
kvalita 60, asi 0,7 MB). Kód a signaturu knihy najdeš v ARON (název souboru snímku „CZ_215000010_00190_<kód>_…_sign-<sign>“).
Hotové soubory přeskočí, takže jde přerušit a pustit znovu. Víc procesů (0/4, 1/4, …) si dělí sdílený limit slusne.py,
stahování tím nezrychlí nad limit.
"""
import io
import os
import sys
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rzip import RangeFile  # noqa: E402

code, sign, out, prefix = sys.argv[1:5]
width = int(sys.argv[5]) if len(sys.argv) > 5 else 2400
quality = int(sys.argv[6]) if len(sys.argv) > 6 else 60
worker, workers = map(int, (sys.argv[7] if len(sys.argv) > 7 else "0/1").split("/"))
url = f"https://storage.vychodoceskearchivy.cz/matriky/{code[0]}/CZ_215000010_00190_{code}_sign-{sign}.zip"
os.makedirs(out, exist_ok=True)
for attempt in range(5):
    try:
        z = zipfile.ZipFile(io.BufferedReader(RangeFile(url), buffer_size=1 << 16))
        names = sorted(z.namelist())
        for k, name in enumerate(names, 1):
            p = os.path.join(out, f"{prefix}_{k:04d}.jpg")
            if (k - 1) % workers != worker or os.path.exists(p):
                continue
            im = Image.open(io.BytesIO(z.read(name))).convert("L")
            if im.width > width:
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            im.save(p + ".part", "JPEG", quality=quality)
            os.replace(p + ".part", p)
            if k % 25 == 0:
                print(k, "/", len(names), flush=True)
        print("hotovo", len(names), flush=True)
        break
    except Exception as e:  # síť VČA občas vypadne; další pokus naváže na hotové soubory
        print("znovu", attempt, repr(e)[:200], flush=True)
