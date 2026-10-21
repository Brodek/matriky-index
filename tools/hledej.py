"""Searches the machine OCR text of all indexed books (knihy/**/ocr-pero.tsv) for a word, tolerating OCR errors.

    python tools/hledej.py <slovo> [--maxd 2] [--kniha KNIHA] [--kontext 1] [--skip REGEX]

Every OCR word (lower-case, without diacritics) is compared with <slovo> on its first len(<slovo>) characters by
Levenshtein distance, because PERO garbles rare surnames (Plocar → „Klozara“, „Plogar“). An empty result does not prove
that a name is missing from a book.
"""
import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
csv.field_size_limit(10_000_000)


def norm(text):
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("slovo")
    parser.add_argument("--maxd", type=int, default=2)
    parser.add_argument("--kniha", help="jen tato kniha (název adresáře, např. dnesice-01)")
    parser.add_argument("--kontext", type=int, default=1, help="kolik řádků nad a pod zásahem vypsat")
    parser.add_argument("--skip", help="regulární výraz slov, která se ignorují, např. '^(ploze|plota)'")
    args = parser.parse_args()
    target = norm(args.slovo)
    skip = re.compile(args.skip) if args.skip else None
    hits = 0
    for path in sorted(REPO.glob("knihy/*/*/ocr-pero.tsv")):
        book = path.parent.name
        if args.kniha and book != args.kniha:
            continue
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        pages = {}
        for row in rows:
            pages.setdefault((row["soubor"], row["strana"]), []).append(row)
        for (image, side), lines in pages.items():
            for i, row in enumerate(lines):
                words = [w for w in re.split(r"[^a-z]+", norm(row["text"])) if len(w) >= len(target) - 1]
                match = next((w for w in words
                              if not (skip and skip.match(w)) and lev(w[: len(target)], target) <= args.maxd), None)
                if not match:
                    continue
                hits += 1
                around = " / ".join(r["text"] for r in lines[max(0, i - args.kontext): i + args.kontext + 1])
                print(f"{path.parent.parent.name}/{book} snímek {row['snimek']}{side} ř.{row['radek']} [{match}] {around}")
    print(f"{hits} zásahů", file=sys.stderr)


if __name__ == "__main__":
    main()
