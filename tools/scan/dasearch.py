"""dasearch.py <query> [searchtype] — DigiArchiv SOA Třeboň search, prints result ids and titles."""
import re, sys, os, html, urllib.request, urllib.parse, http.cookiejar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slusne  # noqa: E402
sys.stdout.reconfigure(encoding="utf-8")
q = sys.argv[1]; st = sys.argv[2] if len(sys.argv) > 2 else ""
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", "Mozilla/5.0")]
B = "https://digi.ceskearchivy.cz/pages/"
u = B + "search.php?" + urllib.parse.urlencode({"userp": 1, "new": 1, "menu": 1, "sst": 1, "id": 0, "doctree": 10, "dates": "", "search": q, "searchtype": st, "date_from": (sys.argv[3] if len(sys.argv)>3 else ""), "date_to": (sys.argv[4] if len(sys.argv)>4 else "")})
h = slusne.urlopen(u, "stranka", timeout=120, opener=op).read().decode("utf-8", "replace")
m = re.search(r'var params = "([^"]+)"', h)
params = m.group(1)
req = urllib.request.Request(B + "search_result.php?id=0&queryid=&doctree=10", data=params.encode(), headers={"Content-type": "application/x-www-form-urlencoded; charset=UTF-8"})
r = slusne.urlopen(req, "stranka", timeout=180, opener=op).read().decode("utf-8", "replace")
open("dares.html", "w", encoding="utf-8").write(r)
t = re.sub(r"<script.*?</script>", "", r, flags=re.S)
for blk in re.split(r"(?=<tr)", t):
    ids = re.findall(r"[?&]id=(\d{3,8})", blk)
    s = html.unescape(re.sub(r"<[^>]+>", " ", blk)); s = re.sub(r"\s+", " ", s).strip()
    if ids and s: print(ids[0], "|", s[:220])
