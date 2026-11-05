#!/usr/bin/env bash
# refresh.sh — rebuild the site and (optionally) deploy.
#
# Two cadences, because the data has two clocks:
#   prices  -> price performance goes stale daily   -> run NIGHTLY
#   full    -> fundamentals change only on filings  -> run WEEKLY
#
# Run this on your Mac or a small VPS — NOT on Hostinger shared hosting.
# It downloads ~2.9GB (weekly) and builds ~6k pages; Hostinger just serves
# the finished static files. Set DEPLOY=1 to push afterward (see deploy.sh).
#
# Cron (build host):
#   30 4 * * *  DEPLOY=1 /path/to/stockfacts/scripts/refresh.sh prices >> ~/sr.log 2>&1
#   0  5 * * 0  DEPLOY=1 /path/to/stockfacts/scripts/refresh.sh full   >> ~/sr.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:-prices}"
log(){ echo "[$(date -u +%FT%TZ)] $*"; }

if [ "$MODE" = "full" ]; then
  log "WEEKLY: refresh fundamentals from SEC bulk archives"
  python -m pipeline.fetch_bulk_zip
  python -m pipeline.build_from_bulk
fi

log "refresh price performance (all companies, throttled ~40min)"
python -m pipeline.fetch_prices --all

log "build site -> dist/"
python build.py

if [ -n "${DEPLOY:-}" ]; then
  log "deploy"
  bash scripts/deploy.sh
fi
log "done ($MODE)"
