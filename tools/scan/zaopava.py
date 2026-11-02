"""Snímky z Digitální badatelny Zemského archivu v Opavě (digi.archives.cz).

Katalog (vyhledávání, seznam snímků) je za ochranou proti robotům a skriptem do něj nejde; cesty k obrázkům se proto
zjistí v prohlížeči funkcí zaoCesty() z tools/pero/zaopava.js. Obrazový server images.archives.cz je volně dostupný
a tento skript z něj složí dlaždice (Zoomify) do JPEG.

    python -I zaopava.py <cesty.json> <outdir> [uroven] [snímky a-b]

cesty.json: {"<snímek>": "CZ-217000010/NAD-165/dao/images/0414/<uuid>.jpg", …} (výstup zaoCesty).
uroven: -1 = plné rozlišení (výchozí), -2 = poloviční, -3 = čtvrtinové. Výstup <outdir>/NNNN.jpg.
"""
import io
import json
import math
import os
import re
import sys
import time

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slusne  # noqa: E402

BASE = "https://images.archives.cz/ximage/matriky/zoomify/cz/archives/"
TILE = 256


def urovne(w, h):
    out = []
    while True:
        out.append((w, h, math.ceil(w / TILE), math.ceil(h / TILE)))
        if w <= TILE and h <= TILE:
            return out[::-1]
        w, h = (w + 1) // 2, (h + 1) // 2


def dlazdice(url):
    # server občas jednotlivé spojení nedokončí; při déletrvajícím výpadku přeruší další pokusy blokace ze slusne.py
    for pokus in range(3):
        try:
            return slusne.urlopen(url, "obrazek", timeout=60).read()
        except slusne.Zablokovano:
            raise
        except OSError:
            if pokus == 2:
                raise
            time.sleep(5)


def stahni(path, uroven, out):
    base = BASE + path
    props = slusne.urlopen(base + "/ImageProperties.xml", "stranka", timeout=60).read().decode()
    w, h = (int(re.search(rf'{k}="(\d+)"', props).group(1)) for k in ("WIDTH", "HEIGHT"))
    lv = urovne(w, h)
    level = len(lv) + uroven if uroven < 0 else uroven
    before = sum(cx * cy for _, _, cx, cy in lv[:level])
    lw, lh, cx, cy = lv[level]
    img = Image.new("RGB", (lw, lh), "white")
    for y in range(cy):
        for x in range(cx):
            n = before + y * cx + x
            tile = dlazdice(f"{base}/TileGroup{n // 256}/{level}-{x}-{y}.jpg")
            img.paste(Image.open(io.BytesIO(tile)), (x * TILE, y * TILE))
    img.save(out, quality=90)
    return img.size


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cesty = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    uroven = int(sys.argv[3]) if len(sys.argv) > 3 else -1
    vyber = None
    if len(sys.argv) > 4:
        vyber = set()
        for a in sys.argv[4].split(","):
            lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
            vyber.update(range(lo, hi + 1))
    os.makedirs(out, exist_ok=True)
    for k in sorted(cesty, key=int):
        if vyber and int(k) not in vyber:
            continue
        p = os.path.join(out, f"{int(k):04d}.jpg")
        if not cesty[k]:
            print(k, "bez cesty – přeskočeno", flush=True)
            continue
        if not os.path.exists(p):
            print(k, stahni(cesty[k], uroven, p), flush=True)


if __name__ == "__main__":
    main()
