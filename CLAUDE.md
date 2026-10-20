# volebny-model

Forecast of Slovak municipal + regional elections 24 Oct 2026; published via GitHub Pages from `docs/`
(repo mareksulik/volby-2026-forecast).

Run: `source venv/bin/activate`, then the pipeline in README.md (prepare_inputs -> forecast -> build_site).
Local preview: `cd docs && python -m http.server 8765`.
Judgement calls go only into `data/inputs/overrides.yaml` (with adj_reason); never edit `data/inputs/races/*.yaml` by hand (generated).
Snapshots in `data/snapshots/` are append-only; the evaluated forecast is the one locked by tag `forecast-lock-2026-10-21`.
