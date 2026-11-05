#!/usr/bin/env bash
# run_update.sh — one unattended update cycle. Called by GitHub Actions.
#   MODE=prices  -> refresh prices only (nightly)
#   MODE=full    -> refresh SEC fundamentals + prices (weekly)
# Produces dist/ and data/audit/. Exits non-zero if the audit blocks deploy,
# which fails the CI job (you get an email) and leaves the live site untouched.
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${MODE:-prices}"
echo "::group::refresh ($MODE)"
if [ "$MODE" = "full" ]; then
  python -m pipeline.fetch_bulk_zip
  python -m pipeline.build_from_bulk
fi
# MODE=build -> rebuild+deploy from already-committed data (no fetch). Used when
# the daily verification task pushes verified_overrides.json / new content.
if [ "$MODE" = "build" ]; then
  echo "build-only: skipping data refresh"
  echo "::endgroup::"
else
# prices: parallel, resumable
python - <<'PY'
import json,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pipeline.prices as P
P.DELAY=0.0
DATA=Path("data"); idx=json.loads((DATA/"index.json").read_text())
pf=DATA/"prices.json"; out=json.loads(pf.read_text()) if pf.exists() else {}
# nightly: re-price everything fresh; keep yesterday's on failure
todo=[r["ticker"] for r in idx]
ok=fail=0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs={ex.submit(P.perf,tk):tk for tk in todo}
    for i,f in enumerate(as_completed(futs),1):
        tk=futs[f]
        try:
            p=f.result()
        except Exception:
            p=None
        if p: out[tk]=p; ok+=1
        else: fail+=1
        if i%500==0: pf.write_text(json.dumps(out))
pf.write_text(json.dumps(out))
print(f"priced ok={ok} fail={fail} total={len(out)}")
PY
echo "::endgroup::"
fi   # end non-build fetch
echo "::group::verify (reconcile each company; writes held list)"
python -m pipeline.verify       # produces data/audit/unverified.json
echo "::endgroup::"
echo "::group::audit (self-check; blocks deploy on failure)"
python -m pipeline.audit        # non-zero exit here aborts the job (set -e)
echo "::endgroup::"
echo "::group::build (verification gate drops held companies)"
python build.py                 # build.py re-runs verify and excludes held
python make_onefile.py 400
echo "::endgroup::"
echo "update cycle complete, MODE=$MODE"
