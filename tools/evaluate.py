"""Post-election evaluation of both models by finishing position (for docs/skore.html).

Input:  data/results/2026.json (official shares, withdrawn candidates excluded), data/comparison.json (Claude + Codex)
Output: data/evaluation.json
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("claude", "codex")


def race_eval(r, res):
    ranked = sorted(res.items(), key=lambda kv: -kv[1])
    preds = {m: {c["name"]: c[m] for c in r["candidates"] if c.get(m)} for m in MODELS}
    row = {"id": r["id"], "name": r["name"], "group": r["group"], "margin": round(ranked[0][1] - ranked[1][1], 2), "top": []}
    for m in MODELS:
        fav = max(preds[m], key=lambda n: preds[m][n]["p_win"])
        row[m] = {"fav": fav, "hit": fav == ranked[0][0], "p_winner": preds[m].get(ranked[0][0], {}).get("p_win", 0.0)}
    for pos, (name, actual) in enumerate(ranked[:3], 1):
        e = {"pos": pos, "name": name, "actual": actual}
        for m in MODELS:
            share = preds[m].get(name, {}).get("share", 0.0)
            e[m] = {"share": share, "err": round(share - actual, 2)}
        row["top"].append(e)
    return row


def summarize(races, scores):
    out = {}
    for m in MODELS:
        by_pos = {p: [abs(t[m]["err"]) for r in races for t in r["top"] if t["pos"] == p] for p in (1, 2, 3)}
        out[m] = {"winners_hit": sum(r[m]["hit"] for r in races), "n": len(races),
                  "mae_by_pos": {p: round(float(np.mean(v)), 1) for p, v in by_pos.items()},
                  "winner_bias": round(float(np.mean([r["top"][0][m]["err"] for r in races])), 1),
                  "misses": [r["id"] for r in races if not r[m]["hit"]], **scores[m]}
        for g in ("kraj", "mesto", "mc"):
            sub = [r for r in races if r["group"] == g]
            out[m][f"hit_{g}"] = [sum(r[m]["hit"] for r in sub), len(sub)]
    return out


def main() -> None:
    results = json.loads((ROOT / "data/results/2026.json").read_text())
    comp = json.loads((ROOT / "data/comparison.json").read_text())
    races = [race_eval(r, results[r["id"]]) for r in comp["races"] if len(results.get(r["id"], {})) > 1]
    out = {"summary": summarize(races, comp["scores"]), "races": races}
    (ROOT / "data/evaluation.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out["summary"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
