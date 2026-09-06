#!/usr/bin/env bash
# Esquema Danko TV: 0.<minor>-AAAAMMDD-HHMM
# minor = meses desde sep-2026 + 1 (oct-2026 -> 0.2)
# major = anos desde 2026 (2027 -> 1.0)
# Uso: ./version.sh [dankoiptv|dankotv]
set -e
MODE="${1:-dankotv}"
Y=$(date +%Y); M=$(date +%m); D=$(date +%Y%m%d-%H%M)
MON_IDX=$(( (10#$Y - 2026) * 12 + (10#$M - 9) ))
if [ "$MON_IDX" -lt 0 ]; then MON_IDX=0; fi
MAJOR=$(( 10#$Y - 2026 ))
MINOR=$(( MON_IDX + 1 ))
if [ "$MODE" = "dankoiptv" ]; then
  # línea 1.x legacy: 1.1<letra>-fecha
  echo "1.1g-$D"
else
  echo "$MAJOR.$MINOR-$D"
fi
