"""Kdo zápis četl a jak spolu souhlasí nezávislá čtení téhož zápisu (precteno.tsv).

Čtení téhož zápisu jsou řádky jedné knihy se stejným snímkem, datem a typem (stejně je seskupuje web indexu).
Nezávislé je čtení jiného člověka: rozhoduje jméno ve sloupci cetl bez modelu, data a ověření; řádky bez jména
a „pe-pan“ četl správce indexu. Víc řádků jednoho čtenáře je jedno čtení.

Stav zápisu: „shoda“, když jména jednoho čtení jsou všechna i ve druhém (kratší čtení může vynechat kmotry nebo
svědky), „rozpor“, když má každé čtení jméno, které ve druhém není. Čtení beze společného jména jsou dva různé zápisy
téhož dne (dvojčata, dvě svatby), ne rozpor. Jména se porovnávají bez diakritiky, se sjednoceným starým pravopisem
(w → v, cz → c, g → j, y → i…), bez ženské přípony -ová a koncové samohlásky pádu, na prvních pět písmen, a latinské
a německé tvary běžných křestních jmen se převedou na české (Joannes = Jan). Stav je jen vodítko: rozhodne sken.
"""
import itertools
import re
import unicodedata

# Jazykový model se v cetl píše jako id/effort (claude-sonnet-5-5/xhigh). Id modelu obsahuje číslici nebo pomlčku
# (o3, gpt-5.2, deepseek-reasoner), aby se nespletlo s jiným textem.
MODEL_EFFORT = re.compile(r"\b(?=[a-z0-9.-]*[0-9-])[a-z][a-z0-9.]*(?:-[a-z0-9.]+)*/([a-z]+|[0-9]+)\b", re.I)
# Produkt smí stát vedle id modelu, který v něm četl („Copilot gpt-4.1/neuvedeno“).
PRODUKT = re.compile(r"\b(chatgpt|copilot|perplexity)\b", re.I)


def ctenar(cetl):
    """Jméno člověka v cetl, bez modelu, data a poznámky v závorce („Jan Novák + claude-opus-5-5/xhigh 2026-11-05“
    → „Jan Novák“); prázdné, když řádek četl jen model."""
    t = re.sub(r"\([^)]*\)", " ", MODEL_EFFORT.sub(" ", cetl))
    t = PRODUKT.sub(" ", re.sub(r"\d{4}(?:-\d{2}){0,2}", " ", t))
    return " ".join(t.replace("+", " ").replace(",", " ").split())


def kdo_cetl(cetl):
    """Čtenář zápisu: člověk z cetl před „ověřil“ („Vlastimil Machek ověřil pe-pan“ → „Vlastimil Machek“); prázdné
    pro správce indexu (řádek bez jména, který četl jen model, nebo „pe-pan“)."""
    kdo = ctenar(re.split(r"\bověřil", cetl)[0]).strip(" ;")
    return "" if kdo == "pe-pan" else kdo


def _tvar(slovo):
    t = unicodedata.normalize("NFKD", slovo.replace("ß", "ss").replace("ſ", "s"))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    for stary, novy in (("tsch", "c"), ("sch", "s"), ("cz", "c"), ("tz", "c"), ("rz", "r"), ("th", "t"), ("ph", "f"),
                        ("ck", "k"), ("w", "v"), ("g", "j"), ("y", "i")):
        t = t.replace(stary, novy)
    return re.sub(r"(.)\1+", r"\1", t)


# Latinské a německé tvary běžných křestních jmen → český tvar (porovnává se po _tvar).
_KRESTNI = {
    "jan": "joannes johannes johann joann ioannes hans", "josef": "josephus joseph", "frantisek": "franciscus franz",
    "vaclav": "wenceslaus venceslaus wenzel", "matej": "matthias mathias", "matous": "matthaeus mathaeus matheus",
    "jiri": "georgius georg", "jakub": "jacobus jakob jacob", "tomas": "thomas", "martin": "martinus",
    "ondrej": "andreas", "vojtech": "adalbertus adalbert", "petr": "petrus peter", "pavel": "paulus paul",
    "antonin": "antonius anton", "michal": "michael", "simon": "simeon", "vavrinec": "laurentius lorenz",
    "bartolomej": "bartholomaeus bartholomeus bartholomaus", "jilji": "aegidius egidius jilg gilg",
    "stepan": "stephanus stefan stephan", "ignac": "ignatius ignaz", "karel": "carolus karl",
    "mikulas": "nicolaus nikolaus niklas", "krystof": "christophorus christoph", "rehor": "gregorius gregor",
    "sebestian": "sebastianus sebastian", "jindrich": "henricus heinrich", "ludvik": "ludovicus ludwig",
    "vit": "vitus veit", "prokop": "procopius", "dominik": "dominicus", "benedikt": "benedictus",
    "leopold": "leopoldus", "jachym": "joachimus joachim", "filip": "philippus philipp", "lukas": "lucas",
    "marek": "marcus markus", "katerina": "catharina katharina catherina", "marie": "maria",
    "magdalena": "majdalena madlena", "dorota": "dorothea dorotha", "rozalie": "rosalia rozalia",
    "tereza": "theresia teresie terezie", "barbora": "barbara", "alzbeta": "elisabetha elisabeth elizabeta",
    "veronika": "veronica", "apolena": "apollonia apolonia", "zuzana": "susanna susana", "anezka": "agnes",
    "marketa": "margaretha margareta", "vorsila": "ursula", "johana": "johanna joanna", "josefa": "josepha",
    "frantiska": "francisca franziska", "klara": "clara", "judita": "judith", "kristina": "christina",
}
KRESTNI = {_tvar(v): _tvar(k) for k, vs in _KRESTNI.items() for v in vs.split()}


def _bez_koncovky(t):
    """Bez ženské přípony a pádové koncovky (Langová, Langovi → lani; Anny → ann)."""
    for konc in ("ova", "ovi", "em", "ou", "a", "e", "i", "o", "u"):
        if t.endswith(konc) and len(t) - len(konc) >= 3:
            return t[: -len(konc)]
    return t


def jmena(osoby):
    """Jména ve sloupci osoby (slova s velkým písmenem, mimo hranaté závorky) v podobě k porovnání."""
    out = set()
    for slovo in re.findall(r"[^\W\d_]+", re.sub(r"\[[^\]]*\]", " ", osoby)):
        if len(slovo) < 2 or not slovo[0].isupper():
            continue
        t = _tvar(slovo)
        t = KRESTNI.get(t) or KRESTNI.get(_bez_koncovky(t)) or t
        out.add(_bez_koncovky(t)[:5])
    return out


def stav(cteni):
    """Stav zápisu z jeho čtení [(cetl, osoby)]: („shoda“ | „rozpor“ | „“, počet čtenářů)."""
    ctenari = {}
    for cetl, osoby in cteni:
        ctenari.setdefault(kdo_cetl(cetl), set()).update(jmena(osoby))
    vysledek = ""
    for a, b in itertools.combinations([s for s in ctenari.values() if s], 2):
        if not a & b:
            continue
        if a <= b or b <= a:
            vysledek = "shoda"
        else:
            return "rozpor", len(ctenari)
    return vysledek, len(ctenari)


def stavy(radky):
    """Stav každého řádku precteno.tsv jedné knihy ([snimek, datum, typ, obec, osoby, ostatni, jistota, cetl, …]),
    ve stejném pořadí: [(stav, počet čtenářů)]."""
    skupiny = {}
    for r in radky:
        skupiny.setdefault((r[0], r[1], r[2]), []).append((r[7], r[4]))
    hotove = {k: stav(v) for k, v in skupiny.items()}
    return [hotove[(r[0], r[1], r[2])] for r in radky]
