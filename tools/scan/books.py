"""zayt.org book search. usage: python -I books.py "<search term>" [max] [--raw]"""
import sys, json, requests
sys.stdout.reconfigure(encoding="utf-8")
term = sys.argv[1]
mx = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 99
q = {"query": {"searchTerm": term, "hasFilters": False}, "range": [0, mx]}
r = requests.get("https://zayt.org/api/books", params={"q": json.dumps(q)}, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
if r.status_code != 200:
    print(r.status_code, r.text[:300]); sys.exit(1)
d = r.json()
print("count", d.get("count"))
for b in d["books"]:
    if "--titles" in sys.argv:
        print(b["full_slug"], b.get("num_pages"), b["title"][:700]); continue
    if "--raw" in sys.argv:
        print(json.dumps({k: v for k, v in b.items() if k != "pages"}, ensure_ascii=False)); continue
    vf = b.get("vademecum_fields") or {}
    place = vf.get("Původce") or vf.get("Název") or ""
    print(b["full_slug"], "|", vf.get("Název", ""), "|", vf.get("Obsah", "")[:120], "| pages", b.get("num_pages"), "| idx" if b.get("is_index") else "", "| alt:", ";".join(b.get("alternate_places") or [])[:150])
if "--titles" in sys.argv:
    pass
