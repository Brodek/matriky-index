"""Acta Publica (Moravský zemský archiv) přes www.mza.cz/actapublica – bez prohlížeče a bez přihlášení.

    python -I mza.py hledat "Hostim"                  # obce: id a název
    python -I mza.py matriky <obec_id>                 # knihy obce: id, N/O/Z, roky, obce, počet snímků
    python -I mza.py info <id>                         # metadata a seznam snímků knihy (uloží se do cache)
    python -I mza.py snimek <id> <n|a-b> <outdir> [sirka]   # stáhne snímky (výchozí plné rozlišení) jako NNNN.jpg
    python -I mza.py url <id> <n> [sirka]              # IIIF adresa snímku
    python -I mza.py pero <id> <a-b> <prefix> [sirka]  # JSON [[soubor, url], …] pro nahrání do PERO přímo z prohlížeče

<id> je číslo z adresy matrika/detail/<id>, ne signatura. Snímky se číslují od 1 jako v prohlížeči. Obrazový server
(iipsrv) bere jen HTTP/2 a posílá CORS, takže ho stránka PERO může číst přímo. Všechny dotazy jdou přes slusne.py.
"""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slusne  # noqa: E402

BASE = "https://www.mza.cz/actapublica/"
CACHE = Path.home() / ".cache" / "rodokmen-mza"


def page(path, ajax=False):
    req = urllib.request.Request(BASE + path)
    if ajax:
        req.add_header("X-Requested-With", "XMLHttpRequest")
    return slusne.urlopen(req, "stranka", timeout=90).read().decode("utf-8", "replace")


def text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def hledat(name):
    for o in json.loads(page("ajax/matrika/autocomplete_obec?term=::all::" + urllib.parse.quote(name), ajax=True)):
        print(o["id"], o["label"])


def matriky(obec):
    if not obec.isdigit():
        found = json.loads(page("ajax/matrika/autocomplete_obec?term=::all::" + urllib.parse.quote(obec), ajax=True))
        obec = found[0]["id"]
    n = 1
    while True:
        h = page(f"matrika/hledani_obec?typ=obec&obec_id={obec}" + (f"&page={n}" if n > 1 else ""))
        rows = [r for r in re.findall(r"<tr.*?</tr>", h, re.S) if "matrika/detail/" in r]
        for r in rows:
            cells = [text(c) for c in re.findall(r"<td.*?</td>", r, re.S)]
            bid = re.search(r"matrika/detail/(\d+)", r).group(1)
            druhy = []
            for kind, c in zip("NOZ", cells[2:5]):
                years = re.findall(r"\d{4}", c)
                if years:
                    # rejstřík má v tabulce roky ve druhém sloupci, tj. buňka začíná pomlčkou
                    druhy.append(("index " if c.strip().startswith("-") else "") + kind + " " + "-".join(years))
            print(bid, "|", cells[1][:30], "|", ", ".join(druhy),
                  "|", cells[5][:70], "|", cells[6], "snímků")
        if not rows or f"page={n + 1}" not in h:
            break
        n += 1


def info(bid, quiet=False):
    f = CACHE / f"{bid}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
    else:
        h = page(f"matrika/detail/{bid}")
        seg = h[h.find("CreateSeadragon("):]
        arrs = re.findall(r"\[(.*?)\]", seg, re.S)[:3]
        urls = [u.replace("\\/", "/").replace("Deepzoom=", "IIIF=")[:-4] for u in re.findall(r'"([^"]+)"', arrs[0])]
        stav = re.findall(r'"([^"]*)"', arrs[2]) if len(arrs) > 2 else []
        meta = {text(k): text(v) for k, v in re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", h, re.S)}
        d = {"id": bid, "url": BASE + f"matrika/detail/{bid}", "iiif": urls, "stav": stav, "meta": meta}
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    if not quiet:
        for k, v in d["meta"].items():
            print(f"{k}: {v[:150]}")
        print("snímků:", len(d["iiif"]), "| neveřejné:", sum(1 for s in d["stav"] if s and s != d["stav"][0]))
    return d


def iiif(bid, n, sirka=None):
    return info(bid, quiet=True)["iiif"][n - 1] + f"/full/{f'{sirka},' if sirka else 'full'}/0/default.jpg"


def rozsah(spec):
    out = []
    for a in spec.split(","):
        lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
        out += range(lo, hi + 1)
    return out


def snimek(bid, spec, out, sirka=None):
    import httpx
    os.makedirs(out, exist_ok=True)
    with httpx.Client(http2=True, headers={"User-Agent": slusne.UA}, timeout=180) as c:
        for n in rozsah(spec):
            p = os.path.join(out, f"{n:04d}.jpg")
            if os.path.exists(p):
                continue
            u = iiif(bid, n, sirka)
            slusne.pockej(u, "obrazek")
            r = c.get(u)
            slusne.hlas(u, r.status_code)
            if r.status_code != 200 or r.content[:2] != b"\xff\xd8":
                print(n, "chyba", r.status_code)
                continue
            Path(p).write_bytes(r.content)
            print(n, p, len(r.content))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "hledat":
        hledat(args[0])
    elif cmd == "matriky":
        matriky(args[0])
    elif cmd == "info":
        info(args[0])
    elif cmd == "snimek":
        snimek(args[0], args[1], args[2], args[3] if len(args) > 3 else None)
    elif cmd == "url":
        print(iiif(args[0], int(args[1]), args[2] if len(args) > 2 else None))
    elif cmd == "pero":
        bid, spec, prefix = args[0], args[1], args[2]
        sirka = args[3] if len(args) > 3 else None
        print(json.dumps([[f"{prefix}_{n:04d}.jpg", iiif(bid, n, sirka)] for n in rozsah(spec)]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
