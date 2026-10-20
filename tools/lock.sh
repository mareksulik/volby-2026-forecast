#!/usr/bin/env bash
# Publish and lock the final forecast. Usage: tools/lock.sh [YYYY-MM-DD]
set -euo pipefail
cd "$(dirname "$0")/.."
source venv/bin/activate
DAY="${1:-2026-10-21}"
TAG="forecast-lock-2026-10-21"
SNAP="data/snapshots/${DAY}-final.json"

python tools/prepare_inputs.py
python tools/forecast.py --date "$DAY" --label final >/dev/null
python tools/compare.py
python tools/build_site.py
git add -A
git commit -q -m "Final forecast ${DAY}" || true
COMMIT=$(git rev-parse --short HEAD)
python - "$SNAP" "$COMMIT" "$TAG" <<'EOF'
import datetime as dt, hashlib, json, sys
snap, commit, tag = sys.argv[1:4]
json.dump({"locked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "snapshot": snap,
           "sha256": hashlib.sha256(open(snap, "rb").read()).hexdigest(), "commit": commit, "tag": tag},
          open("data/lock.json", "w"), indent=1)
EOF
python tools/build_site.py
git add -A
git commit -q -m "Lock forecast (${TAG}, snapshot ${SNAP})"
git tag -a "$TAG" -m "Locked forecast before the poll moratorium"
git push -q origin main --tags
sleep 60
for u in "" "data/latest.json" "data/lock.json"; do
  curl -s -o /dev/null -w "archive.org %{http_code} $u\n" "https://web.archive.org/save/https://mareksulik.github.io/volby-2026-forecast/$u" || true
done
curl -sI https://mareksulik.github.io/volby-2026-forecast/ | head -1
