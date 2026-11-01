"""Slušné tempo vůči archivům: sdílený limit dotazů na jeden server pro všechny skripty i souběžné procesy.

    import slusne
    data = slusne.urlopen(url_nebo_request, druh="obrazek", timeout=120).read()   # urllib
    r = slusne.get(url, druh="stranka", params=..., timeout=60)                  # requests
    slusne.pockej(url, druh="stranka")                                            # před vlastním voláním (curl)
    slusne.hlas(url, status)                                                      # po odpovědi s HTTP stavem

    python slusne.py stav          # stav limitů a blokací
    python slusne.py odblokuj <server>

Limity: stránky, hledání a API 1 dotaz za 2 s, obrázky, dlaždice a čtení zipu 5 za 1 s. Po 429 nebo 503 je server
30 minut zablokovaný pro všechny procesy: pockej() pak vyhodí Zablokovano a nic se znovu nezkouší. Po třech
nepovedených spojeních za sebou (server odmítá nebo neodpovídá) je odstavený na 10 minut. Archivy za dávky
rychlých dotazů blokují IP adresu, proto musí každé stahování jít přes tento modul.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

INTERVAL = {"stranka": 2.0, "obrazek": 0.2}
BLOKACE = 30 * 60
SELHANI, PAUZA_SELHANI = 3, 10 * 60
STAV = Path(os.environ.get("SLUSNE_STAV", Path.home() / ".cache" / "rodokmen-slusne"))
UA = "Mozilla/5.0 (rodokmen)"


class Zablokovano(RuntimeError):
    pass


def _host(url):
    if isinstance(url, urllib.request.Request):
        url = url.full_url
    return urllib.parse.urlsplit(url).hostname or "?"


class _Zamek:
    def __init__(self, host):
        STAV.mkdir(parents=True, exist_ok=True)
        self.path = STAV / f"{host}.lock"

    def __enter__(self):
        self.f = open(self.path, "a+b")
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                    return self
                except OSError:
                    time.sleep(0.05)
        import fcntl
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if os.name == "nt":
            import msvcrt
            self.f.seek(0)
            msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        self.f.close()


def _cti(host):
    p = STAV / f"{host}.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _zapis(host, st):
    (STAV / f"{host}.json").write_text(json.dumps(st))


def pockej(url, druh="stranka"):
    """Počká na volné místo pro dotaz na server; u zablokovaného serveru vyhodí Zablokovano."""
    host = _host(url)
    with _Zamek(host):
        st, now = _cti(host), time.time()
        if st.get("blokovano_do", 0) > now:
            raise Zablokovano(f"{host} zablokován do {time.strftime('%H:%M', time.localtime(st['blokovano_do']))}"
                              f" (HTTP {st.get('duvod')})")
        slot = max(now, st.get(druh, 0))
        st[druh] = slot + INTERVAL[druh]
        _zapis(host, st)
    if slot > now:
        time.sleep(slot - now)


def hlas(url, status):
    """Zaznamená odpověď; 429 a 503 zablokují server na 30 minut. status None = spojení selhalo (odmítnuto, vypršelo):
    po třetím selhání za sebou se server odstaví na 10 minut, ať se do nedostupného webu nebuší dál."""
    host = _host(url)
    with _Zamek(host):
        st = _cti(host)
        if status in (429, 503):
            st.update(blokovano_do=time.time() + BLOKACE, duvod=status)
        elif status is None:
            st["selhani"] = st.get("selhani", 0) + 1
            if st["selhani"] >= SELHANI:
                st.update(blokovano_do=time.time() + PAUZA_SELHANI, duvod="nedostupný", selhani=0)
        elif st.get("selhani"):
            st["selhani"] = 0
        else:
            return
        _zapis(host, st)


def urlopen(req, druh="stranka", timeout=120, opener=None):
    """urllib.request.urlopen (nebo opener.open) s čekáním na limit a hlášením odpovědi."""
    if isinstance(req, str):
        req = urllib.request.Request(req)
    if not req.has_header("User-agent"):
        req.add_header("User-Agent", UA)
    pockej(req, druh)
    try:
        r = (opener.open if opener else urllib.request.urlopen)(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        hlas(req, e.code)
        raise
    except (urllib.error.URLError, OSError):
        hlas(req, None)
        raise
    hlas(req, r.status)
    return r


def get(url, druh="stranka", **kw):
    """requests.get s čekáním na limit a hlášením odpovědi."""
    import requests
    kw.setdefault("headers", {}).setdefault("User-Agent", UA)
    pockej(url, druh)
    try:
        r = requests.get(url, **kw)
    except requests.exceptions.RequestException:
        hlas(url, None)
        raise
    hlas(url, r.status_code)
    return r


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["stav"]:
        now = time.time()
        for p in sorted(STAV.glob("*.json")):
            st = json.loads(p.read_text())
            blok = st.get("blokovano_do", 0)
            print(p.stem, f"ZABLOKOVÁN ještě {int((blok - now) / 60)} min (HTTP {st.get('duvod')})" if blok > now else "ok")
    elif sys.argv[1:2] == ["odblokuj"] and len(sys.argv) > 2:
        with _Zamek(sys.argv[2]):
            st = _cti(sys.argv[2])
            st.pop("blokovano_do", None)
            _zapis(sys.argv[2], st)
        print("odblokováno", sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
