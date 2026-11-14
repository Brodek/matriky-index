"""Pomůcky ke čtení skenů: rejstřík po svislých pruzích, kontrast vybledlé strany a mapa knihy z horních okrajů snímků.

    python tools/pruhy.py sloupce <obrázek> [--sloupce 4 | 0.3,0.55,0.8] [--vyrez x0,y0,x1,y1] [--kontrast] [--out SLOŽKA]
    python tools/pruhy.py kontrast <obrázek> [--vyrez x0,y0,x1,y1] [--out SLOŽKA]
    python tools/pruhy.py mapa <obrázek> [<obrázek> ...] [--pas x0,y0,x1,y1] [--sirka 1600] [--out SLOŽKA]

sloupce: rejstřík čtený celý naráz přehlíží jména (sloupec příjmení se čte rychle a jméno vypadne). Strana se rozřeže
  na svislé pruhy (počet stejných, nebo hranice ve zlomcích šířky podle sloupců rejstříku) a každý pruh se čte zvlášť,
  řádek po řádku. „V rejstříku není“ platí až po takovém čtení.
kontrast: šedá kopie s roztaženým kontrastem (2 % nejtmavších a 35 % nejsvětlejších bodů ořízne) pro vybledlé písmo,
  mikrofilm a tužku; stranu nepovažovat za prázdnou, dokud se nezkusí takhle.
mapa: z každého snímku jen pás (výchozí horních 12 %: nadpis vsi, rok, číslo strany) pod sebou s názvem souboru – stavba
  knihy (oddíly po vsích, ročníky, rejstříky) na jednom obrázku místo listování.
Zlomky x0,y0,x1,y1 jsou 0–1 šířky a výšky obrázku (výřezu u sloupce --sloupce). Výstup jde vedle obrázku, nebo do --out.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def zlomky(text, n=4):
    hodnoty = [float(v) for v in text.split(",")]
    if len(hodnoty) != n or not all(0 <= v <= 1 for v in hodnoty):
        sys.exit(f"čekám {n} zlomky 0–1 oddělené čárkou: {text}")
    return hodnoty


def vyrez(img, text):
    if not text:
        return img
    x0, y0, x1, y1 = zlomky(text)
    if x0 >= x1 or y0 >= y1:
        sys.exit("výřez: x0 < x1 a y0 < y1")
    w, h = img.size
    return img.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)))


def kontrast(img):
    return ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=(2, 35))


def hranice(text):
    if "," not in text and "." not in text:
        n = int(text)
        if n < 1:
            sys.exit("--sloupce: aspoň 1")
        return [k / n for k in range(1, n)]
    body = sorted(float(v) for v in text.split(","))
    if not all(0 < v < 1 for v in body):
        sys.exit("--sloupce: hranice jsou zlomky šířky mezi 0 a 1")
    return body


def vystup(obrazek, out, pripona):
    slozka = Path(out) if out else obrazek.parent
    slozka.mkdir(parents=True, exist_ok=True)
    return slozka / f"{obrazek.stem}_{pripona}.jpg"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prikaz", choices=["sloupce", "kontrast", "mapa"])
    ap.add_argument("obrazky", nargs="+", type=Path)
    ap.add_argument("--sloupce", default="4")
    ap.add_argument("--vyrez")
    ap.add_argument("--kontrast", action="store_true")
    ap.add_argument("--pas", default="0,0,1,0.12")
    ap.add_argument("--sirka", type=int, default=1600)
    ap.add_argument("--out")
    a = ap.parse_args()

    if a.prikaz == "mapa":
        pasy = []
        for p in a.obrazky:
            pas = vyrez(Image.open(p).convert("RGB"), a.pas)
            pas = pas.resize((a.sirka, max(1, round(pas.height * a.sirka / pas.width))))
            stitek = Image.new("RGB", (a.sirka, 28), "white")
            ImageDraw.Draw(stitek).text((6, 6), p.name, fill="black")
            pasy += [stitek, pas]
        mapa = Image.new("RGB", (a.sirka, sum(i.height for i in pasy)), "white")
        y = 0
        for i in pasy:
            mapa.paste(i, (0, y))
            y += i.height
        cil = Path(a.out or a.obrazky[0].parent) / "mapa.jpg"
        cil.parent.mkdir(parents=True, exist_ok=True)
        mapa.save(cil, quality=88)
        print(cil, f"{len(a.obrazky)} snímků")
        return

    for p in a.obrazky:
        img = vyrez(Image.open(p).convert("RGB"), a.vyrez)
        if a.prikaz == "kontrast" or a.kontrast:
            img = kontrast(img)
        if a.prikaz == "kontrast":
            cil = vystup(p, a.out, "kontrast")
            img.save(cil, quality=92)
            print(cil)
            continue
        meze = [0.0] + hranice(a.sloupce) + [1.0]
        for k, (x0, x1) in enumerate(zip(meze, meze[1:]), 1):
            cil = vystup(p, a.out, f"s{k}")
            img.crop((round(x0 * img.width), 0, round(x1 * img.width), img.height)).save(cil, quality=92)
            print(cil)


if __name__ == "__main__":
    main()
