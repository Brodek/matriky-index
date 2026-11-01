# Index matrik

Co už bylo z matričních knih přečteno – strojově (PERO OCR) i očima – bez vazby na konkrétní rodokmen. Slouží k tomu,
aby se stejná stránka nemusela znovu stahovat, OCRkovat ani číst, a jednou se dá zveřejnit jako index.

Kromě matrik sem patří i další knihy se jmény: pozemkové (gruntovní) knihy, soupisy poddaných, familiantské knihy. Mají
stejnou strukturu; druh knihy říká pole `druh` v `kniha.yaml` (`matrika`, `pozemková kniha`, `urbář`,
`soupis poddaných`, `sčítání lidu`, `policejní přihlášky`, `familianti`; chybí-li, jde o matriku). Zápisy přečtené dřív
při práci na rodokmenu jsou přenesené se `cetl` = „Claude (z rodokmenu …)“ a odkazem `rodokmen: <id záznamu>`.

Skeny se neukládají (lze je kdykoli stáhnout z archivu). Plné exporty z PERO (PAGE XML s obrysy řádků) jsou mimo git
na Google Disku v `Documents/Dol/rodokmen/pero-exporty/`.

Co v indexu je (knihy, rozsah OCR, počty přečtených zápisů): [PREHLED.md](PREHLED.md), generuje `python tools/prehled.py`.

Licence: nástroje MIT ([LICENSE](LICENSE)), data v `knihy/` CC BY 4.0 ([LICENSE-DATA.md](LICENSE-DATA.md)).

## Struktura

```
knihy/<archiv>/<kniha>/
  kniha.yaml      popis knihy: archiv, název, farnost, roky, obsah (které snímky jsou N/O/Z), odkaz na portál,
                  jak se z čísla souboru dostat na snímek, a pro každé OCR: nástroj, dokument v PERO, model, datum
  stranky.tsv     zpracované stránky: snímek, soubor, rozměry obrázku, počet řádků
  ocr-pero.tsv    strojový text: snímek, soubor, strana (L/R), řádek, obdélník x/y/šířka/výška v pixelech obrázku,
                  jistota (0–1), text – nekontrolovaný, s chybami
  precteno.tsv    zápisy přečtené očima (formát níže)
knihy/testy/      pokusná OCR (výřezy)
tools/
  hledej.py       volné hledání slova ve všech knihách (precteno, OCR s opravami; Levenshtein na začátku slova)
  opravy.py       přidání opravy strojového čtení do opravy.tsv
  pero_import.py  převod exportu z PERO do knihy/…
  prehled.py      vygeneruje PREHLED.md
  pero/           balik.py (skeny do balíků ≤ 9,4 MB), pero.js (nahrávání a export ve stránce PERO) – viz PERO.md
  scan/           stahování skenů: pfl.py, pf64.py (Porta fontium), ebget.py (eBadatelna SOA Praha), da2.py,
                  dasearch.py (DigiArchiv SOA Třeboň), zget.py + rzip.py (VČA Zámrsk; vcakniha.py = celá kniha pro PERO),
                  zayt.py, books.py, bfilter.py (zayt.org), mza.py (Acta Publica, MZA Brno), cr.py (výřez skenu);
                  slusne.py = společný limit dotazů
```

Archivy: `portafontium` (SOA Plzeň), `soapraha` (eBadatelna, kniha = id matriky), `soatrebon`, `vca`, `zayt`, `nacr`,
`mza` (Acta Publica, kniha = id z adresy matrika/detail/<id>), `ahmp`, `familysearch` (kniha = číslo DGS).

Archivy blokují IP adresu po dávce rychlých dotazů. Každé stahování proto jde přes `tools/scan/slusne.py`: stránky
a hledání 1 dotaz za 2 s, obrázky 5 za 1 s, po 429/503 půl hodiny nic (sdíleno mezi procesy, `python -I
tools/scan/slusne.py stav`). Vlastní jednorázové skripty volají `slusne.urlopen()` / `slusne.get()`, ne přímo
`urllib`, `requests` ani `curl`. Souběžné procesy limit nezrychlí – jen se o něj dělí.

## Hledání

    python tools/hledej.py plozar --maxd 2 [--kniha dnesice-01] [--skip '^(ploze|plota)'] [--kontext 1]

PERO komolí vzácná příjmení (Plocar → „Klozara“, „Plogar“), proto volné hledání; prázdný výsledek nedokazuje, že jméno
v knize není. Zásah se ověřuje na skenu (snímek a strana jsou ve výpisu).

## Přidání knihy

Celý postup (skeny podle archivu, nahrání do PERO, rozbor rozložení, volba modelu, export a import) je v
[PERO.md](PERO.md). Zkráceně: skeny do PERO (Porta fontium a Acta Publica přímo z prohlížeče, ostatní z disku),
„Handwritten layout“, OCR „Kurrent (German, Czech)“ pro kurent, „Czech Handwritten“ pro latinku, export, doplnit
`BOOKS` a `EXPORTS` v `tools/pero_import.py` a spustit `python tools/pero_import.py <export.zip>`.

## Vrstvy a opravy

Původní data se nepřepisují, opravy a výklady se přidávají zvlášť:

1. `ocr-pero.tsv` – strojový text, nemění se (při lepším OCR se vymění celý).
2. `opravy.tsv` – opravy strojového čtení: co je na skenu opravdu napsáno (PERO „Plohar“, napsáno „Ploczar“). Oprava je
   ukotvená obdélníkem řádku na skenu, ne jeho číslem, takže přežije nové OCR. Přidává se nástrojem:

       python tools/opravy.py <kniha> <snímek+strana> <řádek> "<jak četl PERO>" "<co je napsáno>" --kdo "agent 2026-10-21"

   Sloupce: snimek, soubor, strana, x, y, sirka, vyska (obdélník řádku), puvodne (prázdné = celý řádek), spravne, kdo,
   jistota.
3. `precteno.tsv` – celé zápisy přečtené očima, doslovně, i s chybami písaře.
4. Výklad (kdo osoba ve skutečnosti je, např. v zápisu „Františka Červená“, ve skutečnosti Barbora Jímalová) do indexu
   nepatří – index drží, co je napsáno; výklad je v rodokmenu (ve sloupci `odkaz` se na něj dá odkázat).

`tools/hledej.py` prohledává `precteno.tsv` (zásah označen „[očima]“) a strojový text s použitými opravami („[opraveno]“;
hledá se i v původním znění).

## precteno.tsv – zápisy přečtené očima

Každý zápis, který člověk nebo agent při práci přečetl, i když se netýká hledané rodiny. Sloupce oddělené tabulátorem,
první řádek hlavička:

| sloupec | obsah |
|---|---|
| snimek | číslo snímku na portálu a strana, např. `124R` |
| datum | datum události, jak je čitelné (`1756-01-14`, `1757-04`, `~1723`) |
| typ | `N` narození/křest, `O` sňatek, `Z` úmrtí/pohřeb, `P` převod gruntu v pozemkové knize (koupě, dědictví, přiženění, odhad), `S` řádek soupisu poddaných, `J` jiné (ohlášky, atestát, rejstřík, familiant, prázdná strana) |
| obec | obec a číslo domu (`Jetenovice 7`); u pozemkové knihy i jméno gruntu (`Velké Hydčice 3, grunt Němcovský`) |
| osoby | hlavní osoby s rolí: `dítě: Ambrož; otec: Matěj Píhr; matka: Ludmila` (u O ženich, nevěsta a jejich rodiče; u P `prodávající: …; kupující: …; výměnkář: …`; u S `hospodář: …; manželka: …; děti: …`) |
| ostatni | kmotři, svědci, povolání, věk, příčina smrti – stručně; u P cena, splátky, výminek, svědci |
| jistota | `vysoká`, `střední`, `nízká`; nejisté čtení v textu značit `[?]` |
| cetl | kdo a kdy (`agent 2026-10-21`) |
| odkaz | volitelně odkaz na zpracovaný záznam jinde (např. v rodokmenu) |
