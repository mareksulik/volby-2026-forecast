#!/usr/bin/env bash
# Download ŠÚ SR open data used by tools/build_national.py (not committed: ~40 MB).
set -euo pipefail
cd "$(dirname "$0")/../" && mkdir -p data/raw/susr && cd data/raw/susr
for f in oso/oso2022/files/OSO2022_SK_csv.zip oso/oso2018/files/OSO_2018_xlsx.zip \
         osk/osk2022/files/OSK2022_SK_csv.zip osk/osk2017/files/OSK_2017_xlsx.zip; do
  curl -sSL -O "https://volby.statistics.sk/$f"
done
for z in *.zip; do mkdir -p "${z%.zip}" && unzip -o -q "$z" -d "${z%.zip}"; done
