"""Body pro Mapu matrik (ondrnovy/mapa-matrik, docs/FORMAT.md) ze zápisů indexu přečtených očima.

    python tools/mapa.py <složka data/ z klonu mapa-matrik> [--souhrn souhrn.md]

Každý řádek N/O/Z v precteno.tsv říká, že na snímku je zápis toho druhu z toho roku – bod mapy bez jmen. Bod
z řádků, které četl správce indexu (cetl bez jména nebo pe-pan), má by "pe-pan", ostatní by "matriky-index"; kdo
četl, zůstává v indexu ve sloupci cetl. Změněné knihy se zapíšou přímo do složky mapy: dřívější body "pe-pan"
a "matriky-index" se nahradí přepočtenými, body ostatních přispěvatelů mapy zůstanou a stejný bod se nezdvojí.
--souhrn zapíše popis změn (knihy, body, čtenáři) pro pull request.
"""
import argparse
import collections
import csv
import datetime
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kontrola import ctenar  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
KNIHY = REPO / "knihy"
INDEX_WEB = "https://pe-pan.github.io/matriky-index"
SPRAVCE = "pe-pan"
NASI = {"", SPRAVCE}
Z_INDEXU = {SPRAVCE, "matriky-index"}
RIM = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
# archiv v indexu → (archive, portal) v mapě
ARCHIVY = {"portafontium": ("soa-plzen", "portafontium"), "soapraha": ("soa-praha", "ebadatelna"),
           "vca": ("soa-zamrsk", "aron"), "soatrebon": ("soa-trebon", "digi-ceskearchivy"),
           "zaopava": ("za-opava", "digi-archives"), "mza": ("mza-brno", "actapublica"),
           "ahmp": ("ahmp", "pragapublica"), "zayt": ("na", "zayt")}
AHMP_FARY = {"ŽKR": "Žižkov – kostel sv. Rocha", "ŽKP": "Žižkov – kostel sv. Prokopa",
             "KAR": "Karlín – sv. Cyril a Metoděj", "SM": "Smíchov – sv. Filip a Jakub"}
# Farnost podle čísla signatury Sbírky matrik VČA (z knih indexu a z rejstříku korporací v ARON).
FARY_VCA = {"8": "Bohuslavice", "14": "Bystré", "15": "Častolovice", "24": "Deštné v Orlických horách", "25": "Dobré",
            "26": "Dobruška", "27": "Dobřany", "100": "Sloupno", "114": "Nové Město nad Metují", "117": "Nový Hrádek",
            "120": "Opočno", "138": "Rokytnice v Orlických horách", "144": "Sedloňov", "147": "Slavoňov",
            "136": "Přepychy", "165": "Týniště nad Orlicí", "171-3": "Velký Uhřínov", "1971": "Česká Třebová",
            "1084": "Damníkov", "1085": "Damníkov", "1086": "Damníkov", "M-28": "Opatov"}


def roky(text):
    return [int(r) for r in re.findall(r"(?<!\d)(1[5-9]\d{2})(?!\d)", str(text or ""))]


def roky_nazvu(nazev):
    """Roky z názvu knihy bez čísel, která roky nejsou (signatura, pořadové číslo, id na portálu, inventář)."""
    return roky(re.sub(r"sign\.:? [^ ,(]+|poř\.\s?č\.\s?\d+|\bid \d+|č\. knihy \d+|inv\.(?: č\.)? \d+|kód \w+", "",
                       str(nazev or "")))


def cista_fara(far, archiv, sign):
    """Jen jméno fary: bez závorek, výčtu obcí, roků, druhu matriky a čísla svazku."""
    f = re.sub(r"\s*\(.*", "", str(far or "")).split(",")[0].split(":")[0].strip()
    f = re.sub(r"^(?:[Mm]atrika|kniha)(?: (?:oddaných|narozených|zemřelých))?\s+", "", f)
    if archiv != "ahmp":
        f = f.split(" – ")[0]
    f = re.sub(r"\s+(?:[NOZ]{1,3}\d*\w*|\d{4}\S*|\d+\w*)$", "", f).strip()
    if archiv == "ahmp" and (f in ("", "AHMP") or f == sign):
        f = AHMP_FARY.get((sign.split() or [""])[0], "")
    return f or None


def fara_vca(sign, nazev, obsah, farnost):
    if farnost:
        return re.sub(r"\s*\(.*", "", str(farnost)).split(",")[0].strip()
    if m := (re.search(r"farnost ([^(,]+?)\s*(?:\(|,|$)", nazev) or
             re.search(r"\bfary? ([A-ZÁČĎÉÍŘŠŤÚŽ]\w+(?: (?:nad|pod|u|v) \w+| [A-ZÁČĎÉÍŘŠŤÚŽ]\w+)*)", obsah)):
        return m[1].strip()
    if sign in FARY_VCA:
        return FARY_VCA[sign]
    cislo = sign.split("-")[0]
    if cislo.isdigit() and (1300 <= int(cislo) <= 1340 or cislo in ("5409", "5411", "5413", "7492")):
        return "Litomyšl"
    if cislo in FARY_VCA:
        return FARY_VCA[cislo]
    if m := re.match(r"[NOZ](?: a index [NOZ])?, ([^,;(]+?)(?: a okolí| a předměstí)?\s*[;(]", obsah):
        return m[1].strip()
    if (m := re.search(r" – ([A-ZÁČĎÉÍŘŠŤÚŽ]\w+(?: \w+)?) [NOZ]{1,3}\b", nazev)) or \
            (not nazev.startswith("Sbírka") and (m := re.match(r"([A-ZÁČĎÉÍŘŠŤÚŽ][\w ]+?)(?:,| [NOZ]\b| rejstřík)", nazev))):
        return m[1].strip()
    return None


def kniha(archiv, d, meta):
    """(portal_id, url, signature, parish) knihy v mapě, nebo None, když kniha do mapy nejde."""
    url, nazev = str(meta.get("url") or ""), str(meta.get("nazev") or "")
    obsah, farnost = str(meta.get("obsah") or ""), meta.get("farnost")
    pred_zavorkou = nazev.split(" (")[0].strip()
    if archiv == "portafontium":
        if "/register/" not in url:
            return None  # pozemkové knihy a urbáře mapa vede jinak (kind)
        pid = url.rstrip("/").split("/")[-1]
        sign = re.sub(r" – .*", "", pred_zavorkou)
        return pid, f"https://www.portafontium.eu/register/soap-pn/{pid}", sign, farnost or re.sub(r" \d+$", "", sign)
    if archiv == "soapraha":
        m = re.search(r"/d/(\d+)", url) or re.search(r"matrikaId/(\d+)", url)
        return (m[1], f"https://ebadatelna.soapraha.cz/pages/MatrikaPage/matrikaId/{m[1]}", pred_zavorkou,
                farnost or re.sub(r" \d+\w*$", "", pred_zavorkou)) if m else None
    if archiv == "vca":
        m = re.search(r"apu/([0-9a-f-]{36})", url)
        s = re.search(r"sign\.:? ([0-9A-Z][\w-]*)", nazev)
        far = fara_vca(s[1], nazev, obsah, farnost) if s else None
        return (m[1], f"https://aron.vychodoceskearchivy.cz/apu/{m[1]}", s[1], far) if m and s and far else None
    if archiv == "soatrebon":
        m = re.search(r"(?:ceskearchivy\.cz/|[?&]id=)(\d+)", url)
        if not nazev:
            return None  # bez názvu knihy nevíme signaturu ani faru
        return (m[1], f"https://digi.ceskearchivy.cz/{m[1]}", pred_zavorkou,
                farnost or re.split(r" (?:[NOZ]{1,3}|rejstřík)\b", pred_zavorkou)[0]) if m else None
    if archiv == "zaopava":
        m = re.search(r"xid=([0-9a-f-]{36})", url)
        if not m or "id skenu" in obsah:
            return None  # snímek je id skenu, ne pořadí snímku
        s = re.search(r"sign\. ([^,()]+)", nazev)
        return (m[1].lower(), url, s[1].strip() if s else pred_zavorkou,
                farnost or re.split(r" (?:[NOZ]{1,3})\b", pred_zavorkou)[0]) if s or pred_zavorkou else None
    if archiv == "mza":
        m = re.search(r"/detail/(\d+)", url)
        return (m[1], url, pred_zavorkou.split(", Acta Publica")[0],
                farnost or pred_zavorkou.split(",")[0].split(" (")[0].split(" N ")[0]) if m else None
    if archiv == "ahmp":
        m = re.search(r"xid=([0-9A-Fa-f]{32})", url)
        s = re.search(r", ([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]{2,5} [NOZ]{1,3}\s?\d+\w*)", nazev)
        return (m[1].upper(), url, s[1] if s else pred_zavorkou, farnost or nazev.split(",")[0]) if m else None
    if archiv == "zayt":
        if not d.name.split("-")[0] in ("n", "o", "z", "no", "nz", "oz", "noz") or not url or not nazev:
            return None  # familiantské knihy a jiné než matriky
        return d.name, url, pred_zavorkou, farnost or pred_zavorkou.split(",")[0]
    return None


def kdo_cetl(cetl):
    """Člověk ze sloupce cetl; prázdné, když četl jen model (i „…, ověřil <model>“)."""
    return " ".join(w for w in ctenar(cetl).split() if w != "ověřil")


def snimek(text):
    """Pořadí snímku na portálu z hodnoty sloupce snimek („124R“, „102-111“, „9L+R“)."""
    m = re.match(r"\s*(\d+)", str(text or ""))
    return int(m[1]) if m and int(m[1]) > 0 else None


def klic(p):
    return (p.get("scan"), p.get("type"), p.get("year"), p.get("year_to"), p.get("place"), p.get("house"))


def rozsir(records, typ, lst):
    vse = [int(r) for r in re.findall(r"\d{4}", str(records.get(typ) or ""))] + lst
    if vse:
        records[typ] = f"{min(vse)}–{max(vse)}" if min(vse) != max(vse) else str(min(vse))


def svazky_z_indexu():
    """{(archive, portal_id): svazek} se všemi body N/O/Z z indexu; a počty vynechaných knih."""
    svazky, vynechane = {}, collections.Counter()
    for ky in sorted(KNIHY.glob("*/*/kniha.yaml")):
        d, archiv = ky.parent, ky.parent.parent.name
        if archiv not in ARCHIVY:
            continue
        meta = yaml.safe_load(ky.read_text(encoding="utf-8")) or {}
        k = kniha(archiv, d, meta)
        p = d / "precteno.tsv"
        if not k or not p.exists():
            vynechane[f"{archiv}: {'nejde převést' if not k else 'bez precteno.tsv'}"] += 1
            continue
        pid, url, sign, far = k
        far = cista_fara(far, archiv, sign)
        if not far:
            vynechane[f"{archiv}: bez fary"] += 1
            continue
        archive, portal = ARCHIVY[archiv]
        sv = svazky.setdefault((archive, pid), {"archive": archive, "portal": portal, "pid": pid, "url": url,
                                                 "sign": sign, "far": far, "roky": [], "druhy": set(), "body": {},
                                                 "zdroje": set(), "ctenari": collections.Counter()})
        if not d.name.endswith("-zo"):  # oddíl -zo téže knihy: popis bereme z hlavní složky
            sv["sign"], sv["far"] = sign, far
        sv["zdroje"].add(f"{archiv}/{d.name}")
        sv["roky"] += roky(meta.get("roky")) or roky_nazvu(meta.get("nazev"))
        with open(p, encoding="utf-8", newline="") as f:
            for r in list(csv.reader(f, delimiter="\t"))[1:]:
                if len(r) < 8 or r[2] not in ("N", "O", "Z"):
                    continue
                s, ry = snimek(r[0]), roky(r[1])
                if not s or not ry:
                    continue
                kdo = kdo_cetl(r[7])
                b = sv["body"].setdefault((s, r[2]), {"roky": [], "mesice": set(), "nasi": False})
                b["roky"] += ry
                b["nasi"] |= kdo in NASI
                if len(ry) == 1 and (m := re.match(r"\d{4}-(\d{2})", r[1])):
                    b["mesice"].add((ry[0], int(m[1])))
                sv["druhy"].add(r[2])
                sv["ctenari"][kdo or SPRAVCE] += 1
    return svazky, vynechane


def body_svazku(sv):
    body = []
    for (s, typ), b in sorted(sv["body"].items()):
        bod = {"scan": s, "type": typ, "year": min(b["roky"])}
        if max(b["roky"]) != bod["year"]:
            bod["year_to"] = max(b["roky"])
        else:
            m = sorted(mes for rok, mes in b["mesice"] if rok == bod["year"])
            if m:
                bod["months"] = RIM[m[0] - 1] if m[0] == m[-1] else f"{RIM[m[0] - 1]}–{RIM[m[-1] - 1]}"
        bod["by"] = SPRAVCE if b["nasi"] else "matriky-index"
        body.append(bod)
    return body


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("mapa", type=Path, help="složka data/ z klonu mapa-matrik")
    ap.add_argument("--souhrn", type=Path)
    a = ap.parse_args()
    dnes = datetime.date.today().isoformat()
    svazky, vynechane = svazky_z_indexu()
    zmeny = []
    for (archive, pid), sv in sorted(svazky.items()):
        body = body_svazku(sv)
        if not body:
            continue
        cil = a.mapa / archive / f"{pid}.json"
        stary = json.loads(cil.read_text(encoding="utf-8")) if cil.exists() else None
        if stary:
            vol = json.loads(json.dumps(stary))
            cizi = [p for p in vol.get("points") or [] if p.get("by") not in Z_INDEXU]
            jejich = {klic(p)[:3] for p in cizi}
            vol["points"] = cizi + [p for p in body if klic(p)[:3] not in jejich]
            vol["points"].sort(key=lambda p: (p.get("scan", 0), str(p.get("type", "")), p.get("year", 0)))
            records = vol.setdefault("records", {})
            for typ in sorted(sv["druhy"]):
                rozsir(records, typ, [y for (s, t), b in sv["body"].items() if t == typ for y in b["roky"]])
            zdroje = vol.setdefault("sources", [])
            if not any(z.get("by") == "matriky-index" for z in zdroje):
                zdroje.append({"by": "matriky-index", "date": dnes})
        else:
            vsechny = sv["roky"] or [r for b in sv["body"].values() for r in b["roky"]]
            rozsah = f"{min(vsechny)}–{max(vsechny)}" if min(vsechny) != max(vsechny) else str(min(vsechny))
            vol = {"schema": 1, "archive": archive, "portal": sv["portal"], "portal_id": pid, "url": sv["url"],
                   "signature": sv["sign"], "parish": sv["far"],
                   "records": {t: rozsah for t in "NOZ" if t in sv["druhy"]}, "points": body,
                   "sources": [{"by": "matriky-index", "date": dnes}]}
            if not sv["roky"]:
                vol["notes"] = ["Roky v records jen podle zápisů přečtených v indexu matrik; kniha může být širší."]
        if vol == stary:
            continue
        stare_body = {klic(p) for p in (stary or {}).get("points") or []}
        nove_body = {klic(p) for p in vol["points"]}
        zmeny.append((archive, pid, sv, stary is None, len(nove_body - stare_body), len(stare_body - nove_body)))
        cil.parent.mkdir(parents=True, exist_ok=True)
        cil.write_text(json.dumps(vol, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    radky = [f"Body z indexu matrik ({INDEX_WEB}), stav k {dnes}: {len(zmeny)} knih "
             f"({sum(1 for z in zmeny if z[3])} nových), +{sum(z[4] for z in zmeny)} / −{sum(z[5] for z in zmeny)} bodů.",
             "", "Body jsou bez jmen: snímek, druh a rok zápisu přečteného v indexu. `by: pe-pan` četl správce indexu, "
             "`by: matriky-index` ostatní přispěvatelé; kdo četl, je v indexu ve sloupci `cetl`. Převádí "
             "`tools/mapa.py` v pe-pan/matriky-index.", "",
             "| kniha | v indexu | body | čtenáři v indexu |", "|---|---|---|---|"]
    for archive, pid, sv, nova, plus, minus in zmeny:
        ctenari = ", ".join(f"{k} ({n})" for k, n in sv["ctenari"].most_common(4))
        zdroje = ", ".join(f"[{z}]({INDEX_WEB}/#kniha/{z})" for z in sorted(sv["zdroje"]))
        radky.append(f"| {archive}/{pid} – {sv['sign']}{' (nová)' if nova else ''} | {zdroje} | +{plus} / −{minus} "
                     f"| {ctenari} |")
    if vynechane:
        radky += ["", "Nepřevedené knihy indexu: " + ", ".join(f"{k} {n}" for k, n in sorted(vynechane.items())) + "."]
    text = "\n".join(radky) + "\n"
    if a.souhrn:
        a.souhrn.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
