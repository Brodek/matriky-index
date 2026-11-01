"""Zabalí skeny pro nahrání do PERO: python -I tools/pero/balik.py <složka_s_jpg> [max_MB]

Nástroje prohlížeče (např. Claude in Chrome) přenesou do stránky nejvýš 10 MB na jedno nahrání. Balík <složka>_baliky/pNNN.pack
spojí víc skenů do jednoho souboru; funkce pripravNahravani() z tools/pero/pero.js ho ve stránce PERO rozbalí.
Formát: 4 bajty délka JSON hlavičky (little endian), hlavička [[jméno, velikost], …], pak data souborů za sebou.
"""
import glob
import json
import os
import struct
import sys

src = sys.argv[1].rstrip("\\/")
limit = float(sys.argv[2]) * 1e6 if len(sys.argv) > 2 else 9.4e6
dst = src + "_baliky"
os.makedirs(dst, exist_ok=True)
packs, cur, size = [], [], 0
for f in sorted(glob.glob(os.path.join(src, "*.jpg"))):
    s = os.path.getsize(f)
    if s > limit:
        print("příliš velký, vynechán:", f)
        continue
    if size + s > limit:
        packs.append(cur)
        cur, size = [], 0
    cur.append((f, s))
    size += s
if cur:
    packs.append(cur)
for i, items in enumerate(packs, 1):
    p = os.path.join(dst, f"p{i:03d}.pack")
    head = json.dumps([[os.path.basename(f), s] for f, s in items]).encode()
    with open(p, "wb") as o:
        o.write(struct.pack("<I", len(head)))
        o.write(head)
        for f, _ in items:
            with open(f, "rb") as data:
                o.write(data.read())
    print(p, len(items), os.path.basename(items[0][0]), "…", os.path.basename(items[-1][0]))
