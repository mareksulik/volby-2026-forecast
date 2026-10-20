"""Claude vs Codex forecast comparison.

1. Freezes a copy of Codex's locked forecast (../volebny-model-codex/docs/data/forecast.json) into data/codex/,
   verifying its sha256 against Codex's data/LOCK.json.
2. Joins races and candidates, writes data/comparison.json (agreement, differences and, once
   data/results/2026.json exists, the same scores for both models).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_inputs import clean_name, norm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CODEX = ROOT.parent / "volebny-model-codex"
CODEX_URL = "https://mareksulik.github.io/volebny-model-codex/"
REGION = {"bratislavsky": "ba", "trnavsky": "tt", "trenciansky": "tn", "nitriansky": "nr", "zilinsky": "za",
          "banskobystricky": "bb", "presovsky": "po", "kosicky": "ke"}


def race_id(codex_id: str) -> str:
    if codex_id.startswith("city-"):
        return "mesto-" + codex_id[5:]
    if codex_id.startswith("borough-bratislava-"):
        return "mc-" + codex_id[len("borough-bratislava-"):]
    if codex_id.startswith("region-"):
        return "kraj-" + REGION[codex_id[7:].replace("-kraj", "")]
    raise ValueError(codex_id)


FROZEN = ["forecast", "polls", "odds", "events", "sources"]


def freeze_codex() -> dict:
    """Copy Codex's locked data files; refuse if any checksum differs from its LOCK.json."""
    lock = json.loads((CODEX / "data/LOCK.json").read_text())
    out = ROOT / "data/codex"
    out.mkdir(parents=True, exist_ok=True)
    for name in FROZEN:
        rel = f"docs/data/{name}.json"
        raw = (CODEX / rel).read_bytes()
        if hashlib.sha256(raw).hexdigest() != lock["files"][rel]:
            raise SystemExit(f"Codex {rel} does not match its LOCK.json checksum")
        (out / f"{name}.json").write_bytes(raw)
    sha = lock["files"]["docs/data/forecast.json"]
    commit = subprocess.run(["git", "-C", str(CODEX), "log", "-1", "--format=%H", "--", "docs/data/forecast.json"],
                            capture_output=True, text=True).stdout.strip()
    meta = {"source": "https://github.com/mareksulik/volebny-model-codex/blob/%s/docs/data/forecast.json" % commit,
            "site": CODEX_URL, "commit": commit, "sha256": sha, "locked_at": lock["locked_at"], "cutoff": lock["cutoff"]}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def key(name: str) -> str:
    return norm(clean_name(name))


def score(rows, results):
    """Same metrics as tools/score.py, for one model given [(race_id, [(name, share, lo, hi, p)])]."""
    br, lg, hit, mae, cov = [], [], 0, [], []
    for rid, cands in rows:
        res = {key(k): v for k, v in (results.get(rid) or {}).items()}
        if len(cands) < 2 or not res:
            continue
        act = np.array([res.get(key(n), 0.0) for n, *_ in cands])
        p = np.array([c[4] for c in cands])
        p = p / p.sum()
        win = np.zeros(len(cands))
        win[act.argmax()] = 1
        br.append(float(((p - win) ** 2).sum()))
        lg.append(float(np.log(max(p[act.argmax()], 1e-3))))
        hit += int(p.argmax() == act.argmax())
        for (n, s, lo, hi, _), a in zip(cands, act):
            mae.append(abs(s - a))
            cov.append(lo <= a <= hi)
    if not br:
        return None
    return {"n": len(br), "brier": round(float(np.mean(br)), 3), "log_score": round(float(np.mean(lg)), 3),
            "favourites_hit": hit, "share_mae_pp": round(float(np.mean(mae)), 2), "coverage_80": round(float(np.mean(cov)), 3)}


def main() -> None:
    meta = freeze_codex()
    codex = json.loads((ROOT / "data/codex/forecast.json").read_text())
    claude = json.loads((ROOT / "data/latest.json").read_text())
    cmap = {race_id(r["id"]): r for r in codex["races"]}
    races, d_share, d_p, agree = [], [], [], 0
    rows_claude, rows_codex = [], []
    for r in claude["races"]:
        x = cmap[r["id"]]
        xc = {key(c["name"]): c for c in x["candidates"] if c["active"]}
        cands = []
        for c in r["candidates"]:
            o = xc.get(key(c["name"]))
            cands.append({"name": c["name"], "inc": c["inc"],
                          "claude": {"share": c["share"], "lo80": c["lo80"], "hi80": c["hi80"], "p_win": c["p_win"]},
                          "codex": None if not o else {"share": round(o["estimate_pct"], 1), "lo80": round(o["low80_pct"], 1),
                                                       "hi80": round(o["high80_pct"], 1), "p_win": round(o["win_probability"], 4)}})
        unmatched = sorted(xc[k]["name"] for k in set(xc) - {key(c["name"]) for c in r["candidates"]})
        both = [c for c in cands if c["codex"]]
        fav_c = max(cands, key=lambda c: c["claude"]["p_win"])
        fav_x = max(both, key=lambda c: c["codex"]["p_win"])
        same = fav_c["name"] == fav_x["name"]
        agree += same
        if len(cands) > 1:
            d_share += [abs(c["claude"]["share"] - c["codex"]["share"]) for c in both]
            d_p += [abs(c["claude"]["p_win"] - c["codex"]["p_win"]) for c in both]
        races.append({"id": r["id"], "name": r["name"], "group": r["group"], "candidates": cands,
                      "fav_claude": fav_c["name"], "fav_codex": fav_x["name"], "same_favourite": same,
                      "max_dp": round(max(abs(c["claude"]["p_win"] - c["codex"]["p_win"]) for c in both), 4),
                      "unmatched_codex": unmatched})
        rows_claude.append((r["id"], [(c["name"], c["claude"]["share"], c["claude"]["lo80"], c["claude"]["hi80"], c["claude"]["p_win"]) for c in cands]))
        rows_codex.append((r["id"], [(c["name"], c["codex"]["share"], c["codex"]["lo80"], c["codex"]["hi80"], c["codex"]["p_win"]) for c in both]))
    out = {"codex": meta, "claude_snapshot": claude["label"], "claude_generated": claude["generated"],
           "n_races": len(races), "same_favourite": agree,
           "mean_abs_share_diff_pp": round(float(np.mean(d_share)), 2), "mean_abs_pwin_diff": round(float(np.mean(d_p)), 3),
           "races": races}
    res_path = ROOT / "data/results/2026.json"
    if res_path.exists():
        results = json.loads(res_path.read_text())
        out["scores"] = {"claude": score(rows_claude, results), "codex": score(rows_codex, results)}
    (ROOT / "data/comparison.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"same favourite {agree}/{len(races)}, mean |Δshare| {out['mean_abs_share_diff_pp']} pp, mean |ΔP| {out['mean_abs_pwin_diff']}")
    for r in sorted(races, key=lambda r: -r["max_dp"])[:10]:
        print(f'  {r["id"]:26s} Claude {r["fav_claude"]:22s} Codex {r["fav_codex"]:22s} max|ΔP| {r["max_dp"]:.2f}', r["unmatched_codex"] or "")


if __name__ == "__main__":
    main()
