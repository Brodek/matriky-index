"""Searches all indexed books for a word, tolerating OCR errors: entries read by eye (precteno.tsv), the scribe's errors
corrected in vyklad.tsv (a hit on the corrected value shows the entry as written) and the machine OCR text
(ocr-pero.tsv and the other readings ocr-<cteni>.tsv) with corrections from opravy.tsv applied (the original OCR text
is searched too).

    python tools/hledej.py <slovo> [--maxd 2] [--kniha KNIHA] [--kontext 1] [--skip REGEX]
                           [--obec REGEX] [--archiv ARCHIV] [--jen-ocima] [--stary-pravopis] [--souhrn] [--json]

Every OCR word (lower-case, without diacritics) is compared with <slovo> on its first len(<slovo>) characters by
Levenshtein distance, because PERO garbles rare surnames (Plocar → „Klozara“, „Plogar“). An empty result does not prove
that a name is missing from a book.

Narrowing the output (a common surname has hundreds of hits across the country – tens of kB, expensive for an AI
assistant): --obec keeps entries whose `obec`, or whose book's nazev/farnost/obsah in kniha.yaml, matches the regular
expression (case and diacritics ignored; OCR lines only by the book); --archiv keeps one archive (folder under knihy/);
--jen-ocima skips the machine OCR text; --souhrn prints hit counts per book instead of the lines; --json prints one
JSON object per hit. --stary-pravopis also searches the older spellings of the word (ř → rz, š → ss/sch,
č → cz/tsch, ž → zs, v → w, j → g, í → y/ie, ý → y/i): Příhoda → przihoda, przyhoda…
"""
import argparse
import csv
import functools
import json
import re
import sys
import unicodedata
from pathlib import Path

from opravy import apply, ocr_files, read_tsv

REPO = Path(__file__).resolve().parent.parent
csv.field_size_limit(10_000_000)


def norm(text):
    text = unicodedata.normalize("NFD", text.replace("ſ", "s").replace("ʃ", "s"))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def lev(a, b, limit=None):
    """Levenshtein distance; with limit, any value above it once no alignment can stay within the limit."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if limit is not None and min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


OLD_SPELLING = [("ř", ("r", "rz")), ("š", ("s", "ss", "sch")), ("č", ("c", "cz", "tsch")), ("ž", ("z", "zs")),
                ("í", ("i", "y", "ie")), ("ý", ("y", "i")), ("v", ("v", "w")), ("j", ("j", "g"))]


def old_spellings(word, limit=24):
    """The word as written in registers of the 17th–19th century (Příhoda → przihoda, przyhoda, pržihoda…)."""
    forms = {word.lower()}
    for new, olds in OLD_SPELLING:
        for f in sorted(forms):
            if new in f:
                for old in olds:
                    if len(forms) < limit:
                        forms.add(f.replace(new, old))
    return sorted({norm(f) for f in forms})


def book_text(folder):
    """nazev, farnost and obsah of a book (kniha.yaml) for --obec, without the yaml dependency."""
    path = folder / "kniha.yaml"
    if not path.exists():
        return ""
    keep = re.findall(r"^(?:nazev|farnost|obsah):\s*(.*)$", path.read_text(encoding="utf-8"), re.M)
    return norm(" ".join(keep))


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console defaults to cp1252
    parser = argparse.ArgumentParser()
    parser.add_argument("slovo")
    parser.add_argument("--maxd", type=int, default=2)
    parser.add_argument("--kniha", help="jen tato kniha (název adresáře, např. dnesice-01)")
    parser.add_argument("--kontext", type=int, default=1, help="kolik řádků nad a pod zásahem vypsat")
    parser.add_argument("--skip", help="regulární výraz slov, která se ignorují, např. '^(ploze|plota)'")
    parser.add_argument("--obec", help="jen zápisy z obcí (sloupec obec nebo nazev/farnost/obsah knihy), regulární výraz "
                                       "bez ohledu na diakritiku, např. 'choce|slatin'")
    parser.add_argument("--archiv", help="jen tento archiv (adresář v knihy/, např. vca, mza)")
    parser.add_argument("--jen-ocima", action="store_true", help="bez strojového textu (OCR)")
    parser.add_argument("--stary-pravopis", action="store_true", help="hledat i staré podoby slova (ř → rz, w místo v…)")
    parser.add_argument("--souhrn", action="store_true", help="místo řádků jen počty zásahů po knihách")
    parser.add_argument("--json", action="store_true", help="jeden objekt JSON na zásah")
    args = parser.parse_args()
    targets = old_spellings(args.slovo) if args.stary_pravopis else [norm(args.slovo)]
    shortest = min(len(t) for t in targets)
    longest = max(len(t) for t in targets)
    skip = re.compile(args.skip) if args.skip else None
    place = re.compile(norm(args.obec)) if args.obec else None
    hits = 0
    per_book = {}

    # The same word beginnings recur millions of times in the OCR text; each is compared once
    # (cached by the beginning as long as the longest spelling, cut to each spelling inside).
    @functools.cache
    def close(prefix):
        return any(lev(prefix[: len(t)], t, args.maxd) <= args.maxd for t in targets)

    def found(text):
        words = [w for w in re.split(r"[^a-z]+", norm(text)) if len(w) >= shortest - 1]
        return next((w for w in words if not (skip and skip.match(w)) and close(w[:longest])), None)

    def report(where, snimek, kind, match, line, obec=None):
        """Prints a hit (or only counts it for --souhrn); skips it when --obec matches neither the entry nor the book."""
        nonlocal hits
        if place and not (place.search(norm(obec or "")) or place.search(book_place)):
            return
        hits += 1
        counts = per_book.setdefault(where, {"ocima": 0, "vyklad": 0, "ocr": 0})
        counts[kind] += 1
        if args.souhrn:
            return
        if args.json:
            print(json.dumps({"kniha": where, "snimek": snimek, "druh": kind, "shoda": match, "text": line},
                             ensure_ascii=False))
        else:
            print(line)

    for folder in sorted(p for p in REPO.glob("knihy/*/*") if p.is_dir()):
        book = folder.name
        if args.kniha and book != args.kniha:
            continue
        if args.archiv and folder.parent.name != args.archiv:
            continue
        where = f"{folder.parent.name}/{book}"
        book_place = book_text(folder) if place else ""
        vyklady = {}
        for v in read_tsv(folder / "vyklad.tsv"):
            vyklady.setdefault((v["snimek"], v["datum"]), []).append(v)
        entries = {}
        villages = {}
        for row in read_tsv(folder / "precteno.tsv"):
            text = " | ".join(row.get(k, "") for k in ("datum", "typ", "obec", "osoby", "ostatni"))
            entries.setdefault((row["snimek"], row["datum"]), text)
            villages.setdefault((row["snimek"], row["datum"]), row.get("obec", ""))
            note = "".join(f" [výklad: {v['udaj']} „{v['napsano']}“ → „{v['spravne']}“]"
                           for v in vyklady.get((row["snimek"], row["datum"]), []))
            match = found(text)
            if match:
                report(where, row["snimek"], "ocima", match,
                       f"{where} snímek {row['snimek']} [očima]{note} [{match}] {text}", row.get("obec"))
        for (snimek, datum), rows in vyklady.items():
            for v in rows:
                match = found(v["spravne"])
                if match:
                    entry = entries.get((snimek, datum), datum)
                    report(where, snimek, "vyklad", match,
                           f"{where} snímek {snimek} [výklad] [{match}] {v['udaj']}: napsáno „{v['napsano']}“, správně "
                           f"„{v['spravne']}“ (doklady: {v['doklady']}) | {entry}", villages.get((snimek, datum), ""))
        if args.jen_ocima or (place and not place.search(book_place)):  # OCR lines carry no village: only by book
            continue
        for ocr in ocr_files(folder):
            label = "" if ocr.name == "ocr-pero.tsv" else f" [{ocr.stem.removeprefix('ocr-')}]"
            rows = read_tsv(ocr)
            for row in rows:  # the test crops (knihy/testy) have "vyrez" instead of "soubor", no "snimek" or "strana"
                row.setdefault("soubor", row.get("vyrez", ""))
                row.setdefault("snimek", "")
                row.setdefault("strana", "")
            rows = apply(rows, read_tsv(folder / "opravy.tsv"))
            pages = {}
            for row in rows:
                pages.setdefault((row["soubor"], row["strana"]), []).append(row)
            for (image, side), lines in pages.items():
                for i, row in enumerate(lines):
                    match = found(row["text"]) or (found(row["text_ocr"]) if "text_ocr" in row else None)
                    if not match:
                        continue
                    around = " / ".join(r["text"] for r in lines[max(0, i - args.kontext): i + args.kontext + 1])
                    fixed = " [opraveno]" if "text_ocr" in row else ""
                    report(where, row["snimek"], "ocr", match,
                           f"{where}{label} snímek {row['snimek']}{side} ř.{row['radek']}{fixed} [{match}] {around}")
    if args.souhrn:
        for where, c in sorted(per_book.items(), key=lambda x: -sum(x[1].values())):
            if args.json:
                print(json.dumps({"kniha": where, **c}, ensure_ascii=False))
            else:
                print(f"{where}\točima {c['ocima']}\tvýklad {c['vyklad']}\tOCR {c['ocr']}")
    print(f"{hits} zásahů" + (f" v {len(per_book)} knihách" if per_book else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
