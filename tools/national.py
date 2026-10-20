"""National party swing since the 2022 local elections: mean of national polls Sep-Oct 2026 vs Sep-Nov 2022."""
import json
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
MAP = {"PS": ["PS"], "SMER": ["Smer-SD"], "HLAS": ["Hlas-SD"], "SNS": ["SNS"], "SAS": ["SaS"], "KDH": ["KDH"],
       "SLOVENSKO": ["Hnutie Slovensko", "OLaNO"], "REPUBLIKA": ["Republika"], "SR": ["Sme rodina"],
       "ALIANCIA": ["Madarska aliancia", "Aliancia"], "ZL": ["Za ludi"]}


def avg(polls, keys):
    vals = [next((p["results"][k] for k in keys if k in p["results"]), None) for p in polls]
    vals = [v for v in vals if v is not None]
    return round(float(np.mean(vals)), 2) if vals else None


def main():
    ctx = json.loads((ROOT / "data/research/context.json").read_text())
    now, then = ctx["national_polls"], ctx["national_polls_2022"]
    out = {"note": "mean of national voting-intention polls; y2022 = Sep-Nov 2022, y2026 = Sep-Oct 2026",
           "sources": sorted({p["source"] for p in now + then if p.get("source")}), "parties": {}}
    for k, keys in MAP.items():
        out["parties"][k] = {"y2022": avg(then, keys), "y2026": avg(now, keys)}
    (ROOT / "data/inputs/national.yaml").write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False))
    for k, v in out["parties"].items():
        print(k, v)


if __name__ == "__main__":
    main()
