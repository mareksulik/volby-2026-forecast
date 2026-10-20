# Voľby 2026: predpoveď komunálnych a krajských volieb na Slovensku

Pravdepodobnostná predpoveď 33 volieb zo spojených komunálnych a krajských volieb **24. 10. 2026**:
8 predsedov samosprávnych krajov, 8 primátorov krajských miest a 17 starostov mestských častí Bratislavy.
Pre každého kandidáta zverejňujeme odhad podielu hlasov, 80 % interval a pravdepodobnosť výhry.

- Web: https://mareksulik.github.io/volby-2026-forecast/
- Pravidlá a zamknutie: `docs/pravidla.html`. Hodnotená je verzia zamknutá 21. 10. 2026 o 23:59 (tag `forecast-lock-2026-10-21`).
- Snapshoty (append-only): `data/snapshots/`, posledný: `data/latest.json`
- Porovnanie s nezávislým modelom Codex: `docs/porovnanie.html` (Codexova predpoveď je zamrazená v `data/codex/`, kontrolné súčty overuje `tools/compare.py` voči jeho `LOCK.json`)

Inšpirované predpoveďou senátnych volieb 2026 od Josefa Šlerku ([senat-2026-forecast](https://github.com/josefslerka/senat-2026-forecast)), prispôsobené slovenským pravidlám: jedno kolo, vyhráva relatívna väčšina, aj pri županoch.

## Model v skratke

1. **Fundamenty.** Podmienený logit podielov nafitovaný na 2 914 komunálnych voľbách 2018 → 2022 (ŠÚ SR): obhajca, interakcia obhajcu s veľkosťou obce, minulý podiel, nezávislý kandidát, počet strán a povolanie z hlasovacieho lístka. Validácia 5-násobnou krížovou validáciou: Brier 0,43 oproti 0,48 pri pravidle „vyhrá obhajca“, favorit trafený v 72 % volieb, pokrytie 80 % intervalov 82 %.
2. **Celoštátny posun strán:** κ × ln(prieskumy 2026 / prieskumy 2022).
3. **Zdokumentované úpravy** pri faktoch, ktoré model nevidí (`data/inputs/overrides.yaml`, každá so zdôvodnením).
4. **Prieskumy:** váhované podľa veľkosti vzorky a čerstvosti, kombinované s fundamentmi podľa presnosti.
5. **Monte Carlo:** 20 000 simulácií so spoločným celoštátnym šokom vládneho a opozičného bloku. Pravdepodobnosť výhry sa mieša s kurzmi bez marže.

## Reprodukcia

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
tools/fetch_data.sh                # ŠÚ SR open data
python tools/build_national.py     # dataset 2018 → 2022
python tools/fundamentals.py       # fit + validácia -> data/model/fundamentals.json
python tools/national.py           # celoštátny posun strán
python tools/prepare_inputs.py     # výskum + overrides -> data/inputs/races/*.yaml
python tools/forecast.py --date 2026-10-21 --label final
python tools/compare.py            # Claude vs Codex -> data/comparison.json
python tools/build_site.py         # -> docs/
python tools/score.py              # po voľbách (data/results/2026.json)
```

Výskum so zdrojmi: `data/research/*.json` (každé číslo má URL). Predpoveď pripravil model Claude, postup kontroloval človek. Nie sú to tipy na stávkovanie.

Licencia: kód MIT (`LICENSE`), obsah a dáta CC BY 4.0 (`LICENSE-CONTENT`).
