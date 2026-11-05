#!/usr/bin/env python3
"""
audit.py — self-audit and guardrails for the autonomous build.

Runs after a data refresh, BEFORE deploy. Its job is to make unattended
updates safe: detect catastrophic parse failures, data corruption, stale
prices, and vanished mega-caps — correct what it can, and REFUSE to publish
when something is clearly wrong (non-zero exit → the CI job fails → you get an
email, and the old site stays up instead of a broken one going live).

Outputs:
  data/audit/report-<UTCDATE>.md   human-readable change + health report
  data/audit/status.json           machine summary {ok, blocked, reasons, ...}
  data/audit/baseline-index.json   snapshot of this index, for next run's diff

Exit code 0 = safe to deploy. Non-zero = blocked; do not deploy.

Usage:
  python -m pipeline.audit                 # audit current data/ vs baseline
  python -m pipeline.audit --no-block      # report only, never block (dry run)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AUD = DATA / "audit"
AUD.mkdir(parents=True, exist_ok=True)

# Mega-caps that must always be present with sane revenue. If one vanishes,
# that's almost always a ticker/CIK change (like XOM's 2026 reincorporation),
# not a real delisting — block and alert so it gets a predecessor-CIK fallback.
CANARY = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "WMT", "UNH", "XOM",
    "JPM", "BRK-B", "V", "MA", "HD", "COST", "CVX", "KO", "PEP", "JNJ",
    "PG", "ABBV", "MRK", "PFE", "BAC", "WFC", "CAT", "BA", "GE", "DIS",
    "NFLX", "CRM", "ORCL", "ADBE", "INTC", "AMD", "T", "VZ", "F", "MCD", "TMO",
]

# Hard thresholds — tune as the universe grows.
MIN_COMPANIES = 5000          # below this, the SEC reprocess likely broke
MAX_COUNT_DROP_FRAC = 0.05    # >5% fewer companies than baseline = suspicious
MIN_PRICE_COVERAGE = 0.85     # fraction of companies that must have prices
MAX_PRICE_STALENESS_DAYS = 5  # newest price as_of must be within N days of today


def _load(p):
    return json.loads(Path(p).read_text()) if Path(p).exists() else None


def _finite_pct(v):
    return v is not None and -10 < v < 10  # margins/returns sane band


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-block", action="store_true",
                    help="report only; always exit 0 (dry run)")
    args = ap.parse_args()

    today = datetime.now(timezone.utc).date()
    idx = _load(DATA / "index.json")
    prices = _load(DATA / "prices.json") or {}
    baseline = _load(AUD / "baseline-index.json")

    reasons = []      # hard failures -> block
    warnings = []     # soft issues -> log only
    corrections = []  # things already auto-fixed upstream

    if not idx:
        reasons.append("index.json missing or empty")
        _write_status(today, False, reasons, warnings, corrections, {})
        print("BLOCK: no index", file=sys.stderr)
        sys.exit(2)

    byt = {r["ticker"]: r for r in idx}
    n = len(idx)

    # 1. count floor
    if n < MIN_COMPANIES:
        reasons.append(f"only {n} companies (floor {MIN_COMPANIES}) — reprocess likely failed")

    # 2. count drop vs baseline
    churn = {}
    if baseline:
        oset, nset = {r["ticker"] for r in baseline}, set(byt)
        added, dropped = sorted(nset - oset), sorted(oset - nset)
        churn = {"added": len(added), "dropped": len(dropped),
                 "added_sample": added[:15], "dropped_sample": dropped[:15]}
        drop_frac = (len(baseline) - n) / len(baseline) if len(baseline) else 0
        if drop_frac > MAX_COUNT_DROP_FRAC:
            reasons.append(f"company count fell {drop_frac*100:.1f}% "
                           f"({len(baseline)}→{n}); >{MAX_COUNT_DROP_FRAC*100:.0f}% drop blocks deploy")

    # 3. canary mega-caps present with sane revenue
    missing_canary, thin_canary = [], []
    for tk in CANARY:
        r = byt.get(tk)
        if not r:
            missing_canary.append(tk)
        elif not r.get("revenue") or r["revenue"] <= 0:
            thin_canary.append(tk)
    if missing_canary:
        reasons.append(f"canary mega-caps missing: {', '.join(missing_canary)} "
                       f"(likely ticker/CIK change — add predecessor-CIK fallback)")
    if thin_canary:
        warnings.append(f"canary present but no revenue: {', '.join(thin_canary)}")

    # 4. price coverage + freshness
    priced = sum(1 for r in idx if r["ticker"] in prices)
    cov = priced / n if n else 0
    if cov < MIN_PRICE_COVERAGE:
        reasons.append(f"price coverage {cov*100:.1f}% < {MIN_PRICE_COVERAGE*100:.0f}% "
                       f"(price source may be blocked/rate-limited)")
    asofs = sorted({v.get("as_of") for v in prices.values() if v.get("as_of")})
    newest = asofs[-1] if asofs else None
    if newest:
        age = (today - datetime.fromisoformat(newest).date()).days
        if age > MAX_PRICE_STALENESS_DAYS:
            reasons.append(f"newest price as_of {newest} is {age}d old "
                           f"(> {MAX_PRICE_STALENESS_DAYS}d) — prices did not refresh")
    else:
        warnings.append("no price as_of dates found")

    # 5. per-field sanity across the universe (corruption smell test)
    bad_rev = [r["ticker"] for r in idx if r.get("revenue") is not None and r["revenue"] < 0]
    # margin sanity only matters for real-revenue companies — micro-caps with
    # near-zero revenue legitimately show enormous margins (net income >> revenue).
    bad_margin = [r["ticker"] for r in idx
                  if (r.get("revenue") or 0) > 1e8
                  and r.get("net_margin") is not None and not _finite_pct(r["net_margin"])]
    future_fy = [r["ticker"] for r in idx if (r.get("fy") or 0) > today.year + 1]
    if len(bad_rev) > 10:
        reasons.append(f"{len(bad_rev)} companies with negative revenue — parse corruption")
    if len(future_fy) > 10:
        reasons.append(f"{len(future_fy)} companies with impossible future fiscal year")
    if bad_margin:
        warnings.append(f"{len(bad_margin)} companies with out-of-band net margin (shown, not blocked)")

    # verification summary (written by pipeline.verify, run just before this)
    held = _load(AUD / "unverified.json") or []
    soft_flags = _load(AUD / "soft-flags.json") or []
    if held:
        warnings.append(f"{len(held)} companies HELD from publish — failed statement "
                        f"reconciliation (see unverified.json; weekly task verifies)")

    ok = len(reasons) == 0
    metrics = {"companies": n, "priced": priced, "price_coverage": round(cov, 4),
               "newest_price_as_of": newest, "churn": churn,
               "bad_revenue": len(bad_rev), "future_fy": len(future_fy),
               "held_unverified": len(held), "soft_flagged": len(soft_flags)}

    _write_report(today, ok, reasons, warnings, corrections, metrics, idx, baseline, byt, prices)
    _write_status(today, ok, reasons, warnings, corrections, metrics)
    # refresh baseline for next run ONLY when we're going to deploy
    if ok:
        (AUD / "baseline-index.json").write_text(json.dumps(
            [{"ticker": r["ticker"], "revenue": r.get("revenue"),
              "fy": r.get("fy"), "name": r.get("name")} for r in idx]))

    print(("OK" if ok else "BLOCK") + f": {n} companies, {priced} priced "
          f"({cov*100:.0f}%), newest price {newest}; "
          f"{len(reasons)} blocker(s), {len(warnings)} warning(s)",
          file=sys.stderr)
    if not ok:
        for r in reasons:
            print("  BLOCKER:", r, file=sys.stderr)
    if ok or args.no_block:
        sys.exit(0)
    sys.exit(1)


def _write_status(today, ok, reasons, warnings, corrections, metrics):
    (AUD / "status.json").write_text(json.dumps({
        "date": today.isoformat(), "ok": ok, "blocked": not ok,
        "reasons": reasons, "warnings": warnings, "corrections": corrections,
        "metrics": metrics,
    }, indent=2))


def _write_report(today, ok, reasons, warnings, corrections, metrics, idx, baseline, byt, prices):
    L = []
    L.append(f"# StocksReviewer — daily audit, {today.isoformat()}")
    L.append("")
    L.append(f"**Verdict: {'✅ SAFE TO DEPLOY' if ok else '⛔ DEPLOY BLOCKED'}**")
    L.append("")
    L.append(f"- Companies: **{metrics['companies']}**")
    L.append(f"- Priced: **{metrics['priced']}** ({metrics['price_coverage']*100:.1f}%)")
    L.append(f"- Newest price as-of: **{metrics['newest_price_as_of']}**")
    L.append(f"- Held from publish (failed verification): **{metrics.get('held_unverified', 0)}** "
             f"· soft-flagged (published): {metrics.get('soft_flagged', 0)}")
    if metrics["churn"]:
        c = metrics["churn"]
        L.append(f"- Universe churn vs last deploy: +{c['added']} / −{c['dropped']}")
    L.append("")
    if reasons:
        L.append("## ⛔ Blockers (deploy refused)")
        for r in reasons:
            L.append(f"- {r}")
        L.append("")
    if warnings:
        L.append("## ⚠️ Warnings (logged, not blocking)")
        for w in warnings:
            L.append(f"- {w}")
        L.append("")
    if metrics.get("churn", {}).get("dropped_sample"):
        L.append("## Dropped tickers (sample)")
        L.append(", ".join(metrics["churn"]["dropped_sample"]))
        L.append("")
    if metrics.get("churn", {}).get("added_sample"):
        L.append("## Added tickers (sample)")
        L.append(", ".join(metrics["churn"]["added_sample"]))
        L.append("")
    # biggest fundamental movers vs baseline (quarter advanced / revenue change)
    if baseline:
        ob = {r["ticker"]: r for r in baseline}
        movers = []
        for tk, r in byt.items():
            o = ob.get(tk)
            if o and o.get("revenue") and r.get("revenue"):
                d = (r["revenue"] - o["revenue"]) / o["revenue"]
                if abs(d) > 0.15:
                    movers.append((tk, r["name"], d, o["revenue"], r["revenue"]))
        movers.sort(key=lambda x: abs(x[2]), reverse=True)
        if movers:
            L.append("## Largest latest-FY revenue changes vs last deploy (>15%)")
            for tk, nm, d, ov, nv in movers[:20]:
                L.append(f"- **{tk}** {nm}: {d*100:+.0f}%  (${ov/1e9:.1f}B → ${nv/1e9:.1f}B)")
            L.append("")
    (AUD / f"report-{today.isoformat()}.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
