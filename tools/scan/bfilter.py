"""usage: python -I bfilter.py "<search>" <year> <col n|o|z> <alt-substring>"""
import sys, json, re, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slusne  # noqa: E402
term, year, col, sub = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4].lower()
out = []
start = 0
while True:
    q = {"query": {"searchTerm": term, "hasFilters": False}, "range": [start, start + 99]}
    d = slusne.get("https://zayt.org/api/books", "stranka", params={"q": json.dumps(q)}, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).json()
    bs = d["books"]
    for b in bs:
        rng = b.get(f"date_ranges_{col}") or ""
        ok = False
        for a, z in re.findall(r"[\[(](\d{4}),(\d{4})[\])]", rng):
            if int(a) <= year < int(z): ok = True
        if not ok: continue
        alts = [x for x in (b.get("alternate_places") or []) + [b.get("place") or ""] if sub in x.lower()]
        if not alts: continue
        print(b["full_slug"], "|", (b.get("vademecum_fields") or {}).get("Název", ""), "|", b["title"][:80], "|", b.get("num_pages"), "|", "; ".join(alts)[:200])
    start += 100
    if start >= (d.get("count") or 0) or not bs: break
