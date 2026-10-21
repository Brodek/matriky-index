"""Converts a PERO OCR export into the index layout: knihy/<archiv>/<kniha>/ocr-pero.tsv, stranky.tsv and kniha.yaml.

    python tools/pero_import.py <export.zip> [--only BOOK]

The export is either PERO's own ZIP (`/document/download_document_pages/<id>`: PAGE XML + TXT per page) or a
`*.pagexml.zip` bundle assembled in the browser ("### PAGE <id>" followed by the page's PAGE XML). Only the text of
each line, its bounding box and confidence are kept; polygons, baselines and PERO's internal ids are dropped.
Book metadata comes from BOOKS below; a book is written only when its pages are found in the export.
"""
import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parent.parent
PF = "https://www.portafontium.eu/register/soap-pn/"

# prefix: the part of the image file name before "_<number>"; delitel: file number // delitel = snímek on the portal.
BOOKS = {
    "dnesice-01": dict(archiv="portafontium", nazev="Dnešice 01", farnost="Dnešice", roky="1685–1735",
                       obsah="N 1685–1735 (snímky 3–151), O 1685–1735 (152–192), Z 1685–1735 (193–247, neOCRováno)",
                       url=PF + "dnesice-01", prefix="dnesice-01"),
    "dnesice-02": dict(archiv="portafontium", nazev="Dnešice 02", farnost="Dnešice", roky="1735–1770",
                       obsah="OCR jen snímky 55–75 (N 1746–1752) a 162–173 (O 1735–1744) – test přesnosti",
                       url=PF + "dnesice-02", prefix="dnesice-02"),
    "dolni-lukavice-01": dict(archiv="portafontium", nazev="Dolní Lukavice 01", farnost="Dolní Lukavice", roky="1682–1765",
                              obsah="N 1682–1765 (snímky 3–370); soubor = snímek×10+1 (354–358: +2)",
                              url=PF + "dolni-lukavice-01", prefix="dolni-lukavice-01"),
    "velky-bor-01": dict(archiv="portafontium", nazev="Velký Bor 01", farnost="Velký Bor", roky="1707–1754",
                         obsah="N 1707–1753 (snímky 2–180), O 1708–1754 (181–228); snímek 135 na serveru prázdný",
                         url=PF + "velky-bor-01", prefix="velky-bor-01"),
    "velky-bor-02": dict(archiv="portafontium", nazev="Velký Bor 02", farnost="Velký Bor", roky="1746–1771",
                         obsah="N 1746–1771 (snímky 4–163); snímek 134 na serveru prázdný",
                         url=PF + "velky-bor-02", prefix="velky-bor-02"),
    "velky-bor-08": dict(archiv="portafontium", nazev="Velký Bor 08", farnost="Velký Bor", roky="1746–1771",
                         obsah="O 1746–1771 (snímky 2–67), řazeno podle obce nevěsty", url=PF + "velky-bor-08",
                         prefix="velky-bor-08"),
    "velky-bor-11": dict(archiv="portafontium", nazev="Velký Bor 11", farnost="Velký Bor", roky="1746–1771",
                         obsah="Z 1746–1771 (snímky 3–89)", url=PF + "velky-bor-11", prefix="velky-bor-11"),
    "maly-bor-05": dict(archiv="portafontium", nazev="Malý Bor 05", farnost="Malý Bor", roky="1745–1763",
                        obsah="N 1745–1763 (snímky 3–99), O (100–141), Z (142–176); navíc soubor 1205-o",
                        url=PF + "maly-bor-05", prefix="maly-bor-05"),
    "maly-bor-03": dict(archiv="portafontium", nazev="Malý Bor 03", farnost="Malý Bor", roky="1704–1726",
                        obsah="N 1704–1726 (snímky 3–69), O (70–85), Z (86–100)", url=PF + "maly-bor-03",
                        prefix="maly-bor-03"),
    "maly-bor-04": dict(archiv="portafontium", nazev="Malý Bor 04", farnost="Malý Bor", roky="1727–1744",
                        obsah="N 1727–1744 (snímky 3–78, mezi nimi listy x; na snímku 72 i oddaní 1728), O (79–93, od 9/1735), Z (94–118)",
                        url=PF + "maly-bor-04", prefix="maly-bor-04"),
    "6568": dict(archiv="soapraha", nazev="Kněževes 03 (eBadatelna 6568)", farnost="Kněževes", roky="1735–1810",
                 obsah="OCR snímky 84–125 (O 1761–1810); soubor = číslo snímku v eBadatelně",
                 url="https://ebadatelna.soapraha.cz/d/6568/", prefix="", delitel=1),
    "o-235": dict(archiv="zayt", nazev="Hrochův Týnec, židovská kontrolní matrika O (NA HBMa inv. 235)",
                  farnost="Hrochův Týnec", roky="1839–1889",
                  obsah="OCR snímky 24–38 (O asi 1846–1856); soubor = snímek; zápisy jsou psané svisle, OCR je z obrázků "
                        "otočených o 90° po směru hodinových ručiček (soubor -r)",
                  url="https://zayt.org/collections/jewish-control-registers-1780-1911/o-235", prefix="o235", delitel=1),
    "o-2434": dict(archiv="zayt", nazev="Zájezdec, židovská matrika O (NA HBMa inv. 2434)", farnost="Zájezdec",
                   roky="1839, 1841–1868",
                   obsah="OCR snímky 22–34; soubor = snímek; zápisy jsou psané svisle, OCR je z obrázků otočených o 90° "
                         "po směru hodinových ručiček (soubor -r)",
                   url="https://zayt.org/collections/jewish-registers-1784-1949/o-2434", prefix="o2434", delitel=1),
    "noz-372": dict(archiv="zayt", nazev="Kostelec nad Černými lesy, židovská kontrolní matrika NOZ (NA HBMa inv. 372)",
                    farnost="Kostelec nad Černými lesy", roky="1840–1862",
                    obsah="N 1840–1862 fol. 1–10 (fol. 9 = sn. 11, fol. 10 = sn. 12), O 1840–1862 fol. 17–19 = sn. 13–15 "
                          "(posty 1–19), Z 1840–1862 fol. 24–30 = sn. 16–22, společný rejstřík N+O+Z (folio/post) pag. "
                          "40–46 = sn. 23–29, sn. 30 závěrečná doložka; OCR snímky 15–31; soubor = snímek",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-372", prefix="noz372",
                    delitel=1),
    "noz-726": dict(archiv="zayt", nazev="Přistoupim, židovská kontrolní matrika NOZ (NA inv. 726)", farnost="Přistoupim",
                    roky="1803–1840",
                    obsah="N 1816–1840 s opisy N 1803, 1805, 1808, O 1826–1838, Z 1819–1839, rejstříky; OCR snímky 2–20 "
                          "(1 a 21 desky); soubor = snímek, obrázek oříznutý na knihu",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-726", prefix="noz726",
                    delitel=1),
    "noz-727": dict(archiv="zayt", nazev="Přistoupim, židovská kontrolní matrika NOZ (NA inv. 727)", farnost="Přistoupim",
                    roky="1840–1858", obsah="N 1841–1858 s rejstříkem, O 1840–1853, Z 1843–1853; OCR snímky 2–13 (1 a 14 "
                                            "desky); soubor = snímek, obrázek oříznutý na knihu",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-727", prefix="noz727",
                    delitel=1),
}
EXPORTS = {  # export file stem -> books it contains, PERO document, model, date
    "dnesice-01": (["dnesice-01"], "c1785e53-4a1c-40f7-a924-7d219217bf15", "Kurrent (German, Czech)", "2026-10-19"),
    "dnesice-02-test": (["dnesice-02"], "103bd7f2-529f-455d-b84e-285b8807397a", "Kurrent (German, Czech)", "2026-10-19"),
    "dolni-lukavice-01": (["dolni-lukavice-01"], "f576fcb5-bc48-406e-b75a-5a0a3b1e2d2c", "Kurrent (German, Czech)",
                          "2026-10-19"),
    "velky-bor-01": (["velky-bor-01"], "658b2c64-93b8-43a8-a478-3cfd30f232fa", "Kurrent (German, Czech)", "2026-10-19"),
    "velky-bor-02": (["velky-bor-02"], "ea0f5d04-f694-4607-a7b3-030028813dbf", "Czech Handwritten", "2026-10-21"),
    "velky-bor-08-11": (["velky-bor-08", "velky-bor-11"], "f61096eb-8434-4bf0-8567-7e488a5ad40a", "Czech Handwritten",
                        "2026-10-21"),
    "maly-bor-05": (["maly-bor-05"], "414ba723-3991-4f8a-b1a5-5c2b4e63bf4a", "Czech Handwritten", "2026-10-21"),
    "maly-bor-03": (["maly-bor-03"], "d6e5e828-1460-4523-8ec1-891a6cad4f26", "Czech Handwritten", "2026-10-21"),
    "maly-bor-04": (["maly-bor-04"], "949bb837-fa4e-4144-a503-65ae049bcf1f", "Czech Handwritten", "2026-10-21"),
    "knezeves-03": (["6568"], "fda952f8-d802-487f-b70a-c278de37df0a", "Czech Handwritten", "2026-10-21"),
    "zidovske-o235-o2434-noz372": (["noz-372"], "17f0a0e2-56cb-476e-beb1-667191362e2a",
                                   "Kurrent (German, Czech)", "2026-10-21"),
    "zidovske-o235-o2434-otocene": (["o-235", "o-2434"], "00b4fec1-aa87-4774-92ec-bd38077992e2", "Kurrent (German, Czech)",
                                    "2026-10-21"),
    "pristoupim-noz726-noz727": (["noz-726", "noz-727"], "3ffd9a97-1756-472a-bc3f-84333d8b10fc", "Kurrent (German, Czech)",
                                 "2026-10-21"),
}


def local(element):
    return element.tag.rsplit("}", 1)[-1]


def child(element, name):
    return next((c for c in element if local(c) == name), None)


def parse_page(xml):
    root = ElementTree.fromstring(xml)
    page = root if local(root) == "Page" else next((e for e in root.iter() if local(e) == "Page"), None)
    if page is None:
        return None
    width, height = int(page.get("imageWidth")), int(page.get("imageHeight"))
    lines = []
    for line in (e for e in page.iter() if local(e) == "TextLine"):
        points = [tuple(map(int, p.split(","))) for p in child(line, "Coords").get("points").split()]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        equiv = child(line, "TextEquiv")
        unicode = child(equiv, "Unicode") if equiv is not None else None
        text = (unicode.text or "") if unicode is not None else ""
        conf = equiv.get("conf", "") if equiv is not None else ""
        lines.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), conf, " ".join(text.split())))
    return page.get("imageFilename").rsplit(".", 1)[0], width, height, lines


def pages(path):
    with zipfile.ZipFile(path) as archive:
        if path.name.endswith(".pagexml.zip"):
            for name in archive.namelist():
                for chunk in archive.read(name).decode("utf-8").split("### PAGE ")[1:]:
                    yield chunk.split("\n", 1)[1].encode("utf-8")
        else:
            for name in sorted(n for n in archive.namelist() if n.endswith(".xml")):
                yield archive.read(name)


def book_of(image, books):
    for key in books:
        prefix = BOOKS[key]["prefix"]
        if not prefix or image.startswith(prefix + "_"):
            return key
    return None


def file_number(image):
    m = re.search(r"(\d{4})(?:-[a-z]+)?$", image)
    return int(m.group(1)) if m else None


def snimek(key, image):
    n = file_number(image)
    if n is None:
        return ""
    return str(n // BOOKS[key].get("delitel", 10))


def write_book(key, export_stem, rows, page_rows, pero_doc, model, date):
    meta = BOOKS[key]
    out = REPO / "knihy" / meta["archiv"] / key
    out.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: (file_number(r[1]) or 0, r[1], r[2], r[4]))
    with open(out / "ocr-pero.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["snimek", "soubor", "strana", "radek", "x", "y", "sirka", "vyska", "jistota", "text"])
        line_no = {}
        for snim, image, side, x, y, wd, ht, conf, text in rows:
            line_no[(image, side)] = line_no.get((image, side), 0) + 1
            w.writerow([snim, image, side, line_no[(image, side)], x, y, wd, ht, conf, text])
    page_rows.sort(key=lambda r: (file_number(r[1]) or 0, r[1]))
    with open(out / "stranky.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["snimek", "soubor", "sirka_obrazku", "vyska_obrazku", "radku"])
        w.writerows(page_rows)
    q = lambda value: json.dumps(value, ensure_ascii=False)  # a JSON string is a valid YAML scalar, colons included
    yaml = [f"archiv: {q(meta['archiv'])}", f"kniha: {q(key)}", f"nazev: {q(meta['nazev'])}", f"farnost: {q(meta['farnost'])}",
            f"roky: {q(meta['roky'])}", f"obsah: {q(meta['obsah'])}", f"url: {q(meta['url'])}",
            "ocr:", f"- nastroj: {q('PERO OCR (pero-ocr.fit.vutbr.cz)')}", f"  dokument: {q(pero_doc)}", f"  model: {q(model)}",
            f"  datum: {q(date)}",
            f"  export: {q(export_stem + ' (plný export: Google Disk, Documents/Dol/rodokmen/pero-exporty)')}",
            f"  stranek: {len(page_rows)}", f"  radku: {len(rows)}",
            f"  poznamka: {q('souřadnice v pixelech nahraného obrázku (viz stranky.tsv); text je strojový, nekontrolovaný')}"]
    (out / "kniha.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")
    print(f"{meta['archiv']}/{key}: {len(page_rows)} stran, {len(rows)} řádků")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    stem = args.export.name.removesuffix(".zip").removesuffix(".pagexml")
    if stem not in EXPORTS:
        sys.exit(f"unknown export {stem}; add it to EXPORTS")
    keys, pero_doc, model, date = EXPORTS[stem]
    rows = {k: [] for k in keys}
    page_rows = {k: [] for k in keys}
    for xml in pages(args.export):
        parsed = parse_page(xml)
        if parsed is None:
            continue
        image, width, height, lines = parsed
        key = book_of(image, keys)
        if key is None:
            print(f"skipping page {image}", file=sys.stderr)
            continue
        snim = snimek(key, image)
        page_rows[key].append([snim, image, width, height, len(lines)])
        for x, y, wd, ht, conf, text in lines:
            rows[key].append((snim, image, "L" if x < width / 2 else "R", x, y, wd, ht, conf, text))
    for key in keys:
        write_book(key, args.export.name, rows[key], page_rows[key], pero_doc, model, date)


if __name__ == "__main__":
    main()
