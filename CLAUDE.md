# volebny-model

Forecast of Slovak municipal + regional elections 24 Oct 2026; published via GitHub Pages from `docs/`
(repo mareksulik/volby-2026-forecast).

Run: `source venv/bin/activate`, then the pipeline in README.md (prepare_inputs -> forecast -> build_site).
Local preview: `cd docs && python -m http.server 8765`.
Judgement calls go only into `data/inputs/overrides.yaml` (with adj_reason); never edit `data/inputs/races/*.yaml` by hand (generated).
Snapshots in `data/snapshots/` are append-only; the evaluated forecast is the one locked by tag `forecast-lock-2026-10-20` (see data/lock.json).
Codex model (sibling repo ../volebny-model-codex, locked): never edit it. `tools/compare.py` freezes its docs/data/*.json into data/codex/ after checking sha256 against its LOCK.json; `tools/codex_view.py` loads it for the site. Site structure: Výsledky (skore.html) · Voľby (volby.html, one page per race with result, Claude and Codex side by side) · Modely (model.html) · Pravidlá · Archív; old URLs (index, codex*, porovnanie) are redirect stubs and must keep working.
Site texts: plain literal Slovak, no metaphors or flourish.
