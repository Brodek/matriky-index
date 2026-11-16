# Číselníky

`ruian_casti_obci.tsv` – části obcí z RÚIAN (kód, název, obec, kód obce, okres). Převzato z Mapy matrik
([ondrnovy/mapa-matrik](https://github.com/ondrnovy/mapa-matrik), `ciselniky/ruian_casti_obci.tsv`, stav k 12. 11. 2026).
Zdroj: ČÚZK, číselníky ISÚI (`UI_CAST_OBCE`, `UI_OBEC`, `UI_OKRES`, https://services.cuzk.cz/sestavy/cis/), otevřená
data pod licencí CC BY 4.0. Obnovení: zkopírovat aktuální soubor z Mapy matrik.

`tools/web.py` podle něj u stejnojmenných obcí pozná okres a soubory obcí na webu pojmenuje `<obec>-<okres>`.
