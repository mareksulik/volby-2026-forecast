"""Score the locked forecast against official results.

Input:  data/results/2026.json  {race_id: {"Candidate name": share_pct, ...}}  (ŠÚ SR, valid votes)
        locked snapshot (data/lock.json -> snapshot) or --snapshot path
Output: data/score.json (per series + per race), printed summary.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SERIES = {"final": "p_win", "bez_trhu": "p_win_blind", "fundamenty": "fund_p_win", "trh": "p_win_market"}


def norm_probs(cands, key):
    p = np.array([c.get(key) or 0.0 for c in cands], dtype=float)
    return p / p.sum() if p.sum() > 0 else None


def score(snapshot: dict, results: dict) -> dict:
    per_series = {s: {"brier": [], "log": [], "hit": []} for s in list(SERIES) + ["obhajca", "rovnomerne"]}
    share_err, fund_err, cover, races = [], [], [], []
    for r in snapshot["races"]:
        res = results.get(r["id"])
        cands = r["candidates"]
        if not res or len(cands) < 2:
            continue
        actual = np.array([res.get(c["name"], 0.0) for c in cands], dtype=float)
        win = np.zeros(len(cands))
        win[actual.argmax()] = 1
        inc = np.array([1.0 if c["inc"] else 0.0 for c in cands])
        probs = {s: norm_probs(cands, k) for s, k in SERIES.items()}
        probs["obhajca"] = inc if inc.sum() else np.full(len(cands), 1 / len(cands))
        probs["rovnomerne"] = np.full(len(cands), 1 / len(cands))
        row = {"id": r["id"], "winner": cands[int(actual.argmax())]["name"]}
        for s, p in probs.items():
            if p is None:
                continue
            per_series[s]["brier"].append(float(((p - win) ** 2).sum()))
            per_series[s]["log"].append(math.log(max(float(p[win == 1][0]), 1e-3)))
            per_series[s]["hit"].append(float(p.argmax() == win.argmax()))
            row[f"p_winner_{s}"] = round(float(p[win == 1][0]), 3)
        for c, a in zip(cands, actual):
            share_err.append(abs(c["share"] - a))
            fund_err.append(abs(c["fund_share"] - a))
            cover.append(c["lo80"] <= a <= c["hi80"])
        races.append(row)
    summary = {s: {"n": len(v["brier"]), "brier": round(float(np.mean(v["brier"])), 3),
                   "log_score": round(float(np.mean(v["log"])), 3), "favourites_hit": int(sum(v["hit"]))}
               for s, v in per_series.items() if v["brier"]}
    return {"series": summary, "share_mae_pp": round(float(np.mean(share_err)), 2),
            "fund_share_mae_pp": round(float(np.mean(fund_err)), 2),
            "coverage_80": round(float(np.mean(cover)), 3), "races": races}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    a = ap.parse_args()
    snap_path = Path(a.snapshot).resolve() if a.snapshot else ROOT / json.loads((ROOT / "data/lock.json").read_text())["snapshot"]
    out = score(json.loads(snap_path.read_text()), json.loads((ROOT / "data/results/2026.json").read_text()))
    out["snapshot"] = str(snap_path.relative_to(ROOT))
    (ROOT / "data/score.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps({k: out[k] for k in ("series", "share_mae_pp", "fund_share_mae_pp", "coverage_80")}, indent=1))


if __name__ == "__main__":
    main()
