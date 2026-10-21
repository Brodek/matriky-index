# Index matrik

Co už bylo z matričních knih přečteno – strojově (PERO OCR) i očima – bez vazby na konkrétní rodokmen. Slouží k tomu,
aby se stejná stránka nemusela znovu stahovat, OCRkovat ani číst, a jednou se dá zveřejnit jako index.

Skeny se neukládají (lze je kdykoli stáhnout z archivu). Plné exporty z PERO (PAGE XML s obrysy řádků) jsou mimo git
na Google Disku v `Documents/Dol/rodokmen/pero-exporty/`.

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
  scan/           stahování skenů: pfl.py, pf64.py (Porta fontium), ebget.py (eBadatelna SOA Praha), da2.py,
                  dasearch.py (DigiArchiv SOA Třeboň), zget.py + rzip.py (VČA Zámrsk), zayt.py, books.py, bfilter.py
                  (zayt.org), cr.py (výřez skenu)
```

Archivy: `portafontium` (SOA Plzeň), `soapraha` (eBadatelna, kniha = id matriky), `soatrebon`, `vca`, `zayt`, `nacr`.

## Hledání

    python tools/hledej.py plozar --maxd 2 [--kniha dnesice-01] [--skip '^(ploze|plota)'] [--kontext 1]

PERO komolí vzácná příjmení (Plocar → „Klozara“, „Plogar“), proto volné hledání; prázdný výsledek nedokazuje, že jméno
v knize není. Zásah se ověřuje na skenu (snímek a strana jsou ve výpisu).

## Přidání knihy

1. Stránky nahrát do PERO (Porta fontium přímo z prohlížeče; ostatní archivy stáhnout skripty z `tools/scan/` a nahrát
   z disku), rozbor rozložení „Handwritten layout“, OCR „Kurrent (German, Czech)“ pro české zápisy, „Czech Handwritten“
   pro latinu.
2. Export: `https://pero-ocr.fit.vutbr.cz/document/download_document_pages/<dokument>` (u velkých knih server vrací 504 –
   pak stránky složit v prohlížeči jako `<kniha>.pagexml.zip`). Plný export uložit na Google Disk.
3. Doplnit knihu do `BOOKS` a `EXPORTS` v `tools/pero_import.py` a spustit `python tools/pero_import.py <export.zip>`.

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
| typ | `N` narození/křest, `O` sňatek, `Z` úmrtí/pohřeb, `J` jiné (ohlášky, atestát, rejstřík, prázdná strana) |
| obec | obec a číslo domu (`Jetenovice 7`) |
| osoby | hlavní osoby s rolí: `dítě: Ambrož; otec: Matěj Píhr; matka: Ludmila` (u O ženich, nevěsta a jejich rodiče) |
| ostatni | kmotři, svědci, povolání, věk, příčina smrti – stručně |
| jistota | `vysoká`, `střední`, `nízká`; nejisté čtení v textu značit `[?]` |
| cetl | kdo a kdy (`agent 2026-10-21`) |
| odkaz | volitelně odkaz na zpracovaný záznam jinde (např. v rodokmenu) |
