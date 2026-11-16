"""Builds the browsable web page (GitHub Pages) of the index into a folder.

    python tools/web.py [--out _site]

Writes <out>/index.html (copied from web/index.html), <out>/data/knihy.json (one entry per book), <out>/data/precteno.json
and <out>/data/vyklad.json (all eye-read entries and interpretations, rows referring to a book by its position in
knihy.json), <out>/data/obce/<obec>.json (one village's eye-read entries and interpretations with their books, so a
search by village need not download precteno.json) with the list of villages <out>/data/obce.json (with vyskyty: archive
and parish of the books the entries come from), and copies knihy/ so the page can load a book's OCR and corrections on
demand. Run by the GitHub Action .github/workflows/pages.yml on every push to main; locally: python tools/web.py &&
python -m http.server -d _site.

Villages of one name: where RÚIAN (ciselniky/ruian_casti_obci.tsv) knows the name in several districts, an entry goes
to <obec>-<okres>.json when its book points to one of them (okres_obce); the rest stay in <obec>.json. An entry read by
several readers carries the state of its readings (cteni.py): "shoda" or "rozpor" and the number of readers.
"""
import argparse
import collections
import csv
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cteni import stavy  # noqa: E402
from mapa import kniha as kniha_mapy  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RUIAN = REPO / "ciselniky" / "ruian_casti_obci.tsv"
csv.field_size_limit(10_000_000)

# Region of the country an archive covers; the national archive and FamilySearch hold books from everywhere.
ARCHIVY = {
    "portafontium": ("SOA Plzeň (Porta fontium)", "západní Čechy"),
    "soatrebon": ("SOA Třeboň (DigiArchiv)", "jižní Čechy"),
    "soapraha": ("SOA Praha (eBadatelna)", "střední Čechy"),
    "ahmp": ("Archiv hl. m. Prahy", "Praha"),
    "konskripce": ("NA – pražské policejní přihlášky", "Praha"),
    "vca": ("SOA Zámrsk (VČA, ARON)", "východní Čechy"),
    "mza": ("Moravský zemský archiv (Acta Publica)", "jižní Morava"),
    "zaopava": ("Zemský archiv v Opavě", "severní Morava a Slezsko"),
    "zayt": ("NA – židovské matriky (zayt.org)", "celé Čechy"),
    "nacr": ("Národní archiv", "celé Čechy"),
    "cuzk": ("ČÚZK – indikační skici", "celé Čechy"),
    "ndk": ("Národní digitální knihovna", "edice a tisky"),
    "familysearch": ("FamilySearch", "různé"),
}


def url_snimku(archiv, kniha, url):
    """Address template of one scan ({snimek}), where the archive's viewer allows it; otherwise empty."""
    if archiv == "zayt":
        return url.split("?")[0] + "?p={snimek}"
    if archiv == "soatrebon" and re.fullmatch(r"\d+", kniha):
        return f"https://digi.ceskearchivy.cz/DA?lang=cs&menu=3&id={kniha}&page={{snimek}}"
    if archiv == "ahmp" and "permalink?xid=" in url:
        return url + "&scan={snimek}"
    return ""


SLOUPCE_PRECTENO = ("snimek", "datum", "typ", "obec", "osoby", "ostatni", "jistota", "cetl", "odkaz")
SLOUPCE_VYKLADU = ("snimek", "datum", "udaj", "napsano", "spravne", "doklady", "kdo", "jistota")
KNIHA_OBCE = ("archiv_nazev", "nazev", "farnost", "druh", "roky", "url", "url_snimku")


def klic_obce(nazev):
    """File name of a village: lower case, without diacritics, other characters as hyphens."""
    ascii_ = unicodedata.normalize("NFKD", nazev.replace("ß", "ss")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def obce_zapisu(obec):
    """Villages of an entry's obec column: {key: name as written, without the house number}.

    A cell can name several villages, separated by ";" or ","; a name not starting with a capital letter ("grunt …",
    "[nečitelné]") is none. The key is the name before any parenthesis, without the house number and "[?]", or the
    parenthesis when the text before it is no name ("nemanželské (Lužná)"); the name as written keeps the parenthesis,
    where the index gives e.g. the present-day name of an old spelling."""
    def cisty(text):
        text = re.sub(r"\([^)]*\)|[\[\]?„“…]", "", text)
        return " ".join(re.sub(r"\s+(?:č\.\s*p\.|čp\.|č\.)?\s*\d.*$", "", text).split())

    out = {}
    for cast in re.split(r"[;,](?![^(]*\))", obec):
        zavorky = re.findall(r"\(([^)]*)\)", cast)
        jak_psano = (cisty(cast) + "".join(f" ({z.strip()})" for z in zavorky)).strip()
        for nazev in [cisty(cast)] + [cisty(z) for z in zavorky]:
            klic = klic_obce(nazev)
            if nazev[:1].isupper() and klic:
                out.setdefault(klic, jak_psano)
                break
    return out


def read_tsv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f, delimiter="\t"))[1:]


def nacti_ruian():
    """{klíč názvu části obce: {okresy}} z ciselniky/ruian_casti_obci.tsv (kod, nazev, obec, obec_kod, okres)."""
    okresy = {}
    for r in read_tsv(RUIAN):
        if len(r) >= 5:
            okresy.setdefault(klic_obce(r[1]), set()).add(r[4])
    return okresy


def obce_knihy(meta, radky, fara):
    """Klíče obcí knihy: ze sloupce obec, z nazev, farnost a obsah v kniha.yaml a z fary, kterou knize přiřazuje převod
    do Mapy matrik (i části „Brno-Líšeň“)."""
    klice = {k for r in radky for k in obce_zapisu(r[3])}
    for text in [str(meta.get(pole) or "") for pole in ("nazev", "farnost", "obsah")] + [fara or ""]:
        for cast in re.split(r"[,;()/]|\s[-–]\s", text):
            for nazev in [cast] + cast.split("-"):
                klice.update(obce_zapisu(nazev))
    return klice


def vaha_okresu(klice, ruian):
    """Váha okresů knihy: obec, kterou RÚIAN zná v jediném okrese, dá okresu 1, víceznačná se dělí rovným dílem."""
    vaha = collections.Counter()
    for k in klice:
        for okres in ruian.get(k, ()):
            vaha[okres] += 1 / len(ruian[k])
    return vaha


def okres_obce(klic, vaha, ruian):
    """Okres obce podle okresů ostatních obcí její knihy, nebo None. Z okresů, kde RÚIAN obec zná, vyhraje ten s největší
    váhou knihy, když má aspoň polovinu váhy nejsilnějšího okresu knihy a víc než ostatní; obec mimo RÚIAN (zaniklá,
    německý tvar, osada) okres nemá."""
    okresy = ruian.get(klic)
    if not okresy or not vaha:
        return None
    poradi = sorted(((vaha.get(o, 0), o) for o in okresy), reverse=True) + [(0, None)]
    (v1, o1), (v2, _) = poradi[0], poradi[1]
    return o1 if v1 >= max(vaha.values()) / 2 and v1 > v2 else None



def cteni(d, ocr):
    """Machine readings of the book for the viewer: [{soubor, stranky, popis}], PERO first."""
    out = []
    for p in sorted(d.glob("ocr-*.tsv"), key=lambda p: (p.name != "ocr-pero.tsv", p.name)):
        suffix = p.stem.removeprefix("ocr-")
        stranky = "stranky.tsv" if suffix == "pero" else f"stranky-{suffix}.tsv"
        info = [o for o in ocr if isinstance(o, dict) and o.get("soubor", "ocr-pero.tsv") == p.name]
        nastroj = str(info[0].get("nastroj", "")).split(" (")[0] if info else suffix
        model = str(info[0].get("model", "")) if info else ""
        snimky = ", ".join(str(o["snimky"]) for o in info if o.get("snimky"))
        out.append({"soubor": p.name, "stranky": stranky,
                    "popis": f"{nastroj}{' – ' + model if model else ''}{' (sn. ' + snimky + ')' if snimky else ''}"})
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO / "_site"))
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)

    ruian = nacti_ruian()
    knihy, precteno, vyklad = [], [], []
    # file key -> {"nazvy": set, "okresy": set, "precteno": [(book index, row, stav, readers)], "vyklad": [(book, row)]}
    obce = {}

    def obec(klic):
        return obce.setdefault(klic, {"nazvy": set(), "okresy": set(), "precteno": [], "vyklad": []})

    cteni_knih = []  # (book index, rows, their states, interpretations, parish, village keys of the book)
    fary = []  # parish of each book as the conversion to Mapa matrik derives it, or None
    for meta_path in sorted(REPO.glob("knihy/*/*/kniha.yaml")):
        d = meta_path.parent
        archiv, kniha = d.parent.name, d.name
        if archiv == "testy":
            continue
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        i = len(knihy)
        rows = [(r + [""])[:9] for r in read_tsv(d / "precteno.tsv") if len(r) >= 8]
        stavy_knihy = stavy(rows)
        for r, (st, n) in zip(rows, stavy_knihy):
            precteno.append([i] + r + ([st, n] if st else []))
        vyklady = [(r + [""])[:8] for r in read_tsv(d / "vyklad.tsv") if len(r) >= 7]
        vyklad += [[i] + r for r in vyklady]
        fara = (kniha_mapy(archiv, d, meta) or (None,) * 4)[3]
        fary.append(fara)
        farnost = klic_obce(re.split(r"[,(]", fara or str(meta.get("farnost") or ""))[0])
        cteni_knih.append((i, rows, stavy_knihy, vyklady, (archiv, farnost) if farnost else None,
                           obce_knihy(meta, rows, fara)))
        rozpory = sum(st == "rozpor" for st, _ in stavy_knihy)
        stranky = [s for p in sorted(d.glob("stranky*.tsv")) for s in read_tsv(p)]
        ocr = meta.get("ocr") or []
        if isinstance(ocr, dict):
            ocr = [ocr]
        roky = [int(m) for r in rows for m in re.findall(r"(?<!\d)(1[4-9]\d\d)(?!\d)", r[1])]
        nazev_archivu, oblast = ARCHIVY.get(archiv, (archiv, "různé"))
        url = str(meta.get("url") or "")
        knihy.append({
            "id": f"{archiv}/{kniha}", "archiv": archiv, "archiv_nazev": nazev_archivu, "oblast": oblast, "kniha": kniha,
            "nazev": str(meta.get("nazev") or kniha), "farnost": str(meta.get("farnost") or ""),
            "druh": str(meta.get("druh") or "matrika"), "roky": str(meta.get("roky") or ""),
            "obsah": str(meta.get("obsah") or ""), "poznamka": str(meta.get("poznamka") or ""), "url": url,
            "mapa": str(meta.get("mapa") or ""), "url_snimku": url_snimku(archiv, kniha, url),
            "precteno": len(rows), "vyklad": sum(1 for v in vyklad if v[0] == i), "rozpory": rozpory,
            "ocr_stran": len({s[0] for s in stranky if s}), "ocr_radku": sum(int(s[4]) for s in stranky if len(s) > 4 and s[4].isdigit()),
            "opravy": len(read_tsv(d / "opravy.tsv")),
            "ocr_model": ", ".join(dict.fromkeys(str(o.get("model", "")) for o in ocr if isinstance(o, dict))),
            "ocr_cteni": cteni(d, ocr),
            "precteno_od": min(roky) if roky else None, "precteno_do": max(roky) if roky else None,
        })

    # A village's district follows the villages of all books of its parish (a book may hold a single village of a
    # parish that crosses a district border).
    obce_farnosti = collections.defaultdict(set)
    for *_, farnost, klice in cteni_knih:
        if farnost:
            obce_farnosti[farnost] |= klice
    for i, rows, stavy_knihy, vyklady, farnost, klice in cteni_knih:
        vaha = vaha_okresu(obce_farnosti[farnost] if farnost else klice, ruian)
        okresy = {}  # village key -> its district by this book
        mista = {}  # (snimek, datum) -> village files, to file an interpretation under its entry's villages
        for r, (st, n) in zip(rows, stavy_knihy):
            for klic, nazev in obce_zapisu(r[3]).items():
                if klic not in okresy:
                    okresy[klic] = okres_obce(klic, vaha, ruian)
                okres = okresy[klic]
                soubor = f"{klic}-{klic_obce(okres)}" if okres and len(ruian[klic]) > 1 else klic
                o = obec(soubor)
                o["nazvy"].add(nazev)
                if okres:
                    o["okresy"].add(okres)
                o["precteno"].append((i, r, st, n))
                mista.setdefault((r[0], r[1]), set()).add(soubor)
        for r in vyklady:
            for soubor in sorted(mista.get((r[0], r[1]), ())):
                obec(soubor)["vyklad"].append((i, r))

    def dump(name, value):
        (out / "data" / name).write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    dump("knihy.json", knihy)
    dump("precteno.json", precteno)
    dump("vyklad.json", vyklad)
    (out / "data" / "obce").mkdir()
    seznam = {}
    for klic in sorted(obce):
        o = obce[klic]
        nazvy = sorted(o["nazvy"])
        okres = {"okres": next(iter(o["okresy"]))} if len(o["okresy"]) == 1 else {}
        dump(f"obce/{klic}.json", {
            "obec": klic, **okres, "nazvy": nazvy,
            "knihy": {knihy[i]["id"]: {k: knihy[i][k] for k in KNIHA_OBCE if knihy[i][k]}
                      for i in sorted({x[0] for x in o["precteno"] + o["vyklad"]})},
            "precteno": [{"kniha": knihy[i]["id"], **{k: v for k, v in zip(SLOUPCE_PRECTENO, r) if v},
                          **({"stav": st, "ctenaru": n} if st else {})} for i, r, st, n in o["precteno"]],
            "vyklad": [{"kniha": knihy[i]["id"], **{k: v for k, v in zip(SLOUPCE_VYKLADU, r) if v}}
                       for i, r in o["vyklad"]],
        })
        # A file can still hold several villages of one name (a name without its district, an old spelling, a
        # hamlet): list where its entries come from, one item per archive and parish of the books (the parish without
        # its villages in parentheses, at most 60 characters; the full one is in the village's file).
        vyskyty = {}
        for i, *_ in o["precteno"]:
            k = knihy[i]
            farnost = re.sub(r"\s*\(.*$", "", k["farnost"]).strip() or fary[i] or k["nazev"]
            misto = (k["archiv"], farnost if len(farnost) <= 60 else farnost[:59].rstrip() + "…")
            v = vyskyty.setdefault(misto, {"archiv": misto[0], "farnost": misto[1], "knihy": set(), "zapisu": 0})
            v["knihy"].add(k["id"])
            v["zapisu"] += 1
        stavy_obce = collections.Counter(st for *_, st, _ in o["precteno"] if st)
        seznam[klic] = {**okres, "nazvy": nazvy, "zapisu": len(o["precteno"]), "vykladu": len(o["vyklad"]),
                        **{k: stavy_obce[s] for k, s in (("shod", "shoda"), ("rozporu", "rozpor")) if stavy_obce[s]}}
        # Where entries come from more than one parish, or RÚIAN knows the name in several districts and none was
        # chosen: there a mix-up is possible.
        if len(vyskyty) > 1 or (not okres and len(ruian.get(klic, ())) > 1):
            seznam[klic]["vyskyty"] = [{**v, "knihy": len(v["knihy"])}
                                       for v in sorted(vyskyty.values(), key=lambda v: (-v["zapisu"], v["farnost"]))]
    dump("obce.json", seznam)
    shutil.copy(REPO / "web" / "index.html", out / "index.html")
    shutil.copytree(REPO / "knihy", out / "knihy", ignore=shutil.ignore_patterns("testy"))
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{out}: {len(knihy)} knih, {len(precteno)} přečtených zápisů, {len(vyklad)} výkladů, {len(obce)} obcí")


if __name__ == "__main__":
    main()
