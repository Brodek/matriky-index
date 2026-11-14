"""pf_snimky.py <kniha> [<kniha> ...] — writes knihy/portafontium/<kniha>/snimky.tsv: the scans of a Porta fontium book in
the portal's order (snimek = position in the portal viewer, 1, 2, 3 …, as in Mapa matrik and the rodokmen skill) with
the image file of each.

<kniha> is the book's folder name; its url comes from kniha.yaml (register, amtsbuch or urbar), otherwise
register/soap-pn/<kniha>. The file numbers in the image names are not scan numbers: a book may skip numbers, add
inserted files (0005-x, 1205-o) or count by ones, so the snímek of a file is only known from this list.
"""
import csv
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slusne  # noqa: E402

KNIHY = Path(__file__).resolve().parents[2] / "knihy" / "portafontium"


def url_of(folder):
    path = folder / "kniha.yaml"
    data = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
    url = str(data.get("url") or f"https://www.portafontium.eu/register/soap-pn/{folder.name}")
    return url.split("?")[0].split("#")[0]


def scans(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    page = slusne.urlopen(request, "stranka", timeout=120).read().decode("utf-8", "replace")
    paths = re.findall(r'data-iip-path="([^"]+)"', page)
    return [Path(p).stem for p in dict.fromkeys(paths)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for name in sys.argv[1:]:
        folder = KNIHY / name
        try:
            stems = scans(url_of(folder))
        except urllib.error.HTTPError as e:
            print(f"{name}: {url_of(folder)} HTTP {e.code}", file=sys.stderr)
            continue
        if not stems:
            print(f"{name}: the portal page lists no scans", file=sys.stderr)
            continue
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "snimky.tsv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(["snimek", "soubor"])
            w.writerows([n, stem] for n, stem in enumerate(stems, 1))
        print(f"{name}: {len(stems)} snímků")


if __name__ == "__main__":
    main()
