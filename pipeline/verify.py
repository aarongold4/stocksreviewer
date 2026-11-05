#!/usr/bin/env python3
"""
verify.py — per-company verification. "Don't publish what can't be verified."

The real risk in an unattended pipeline is not that the SEC's filed number is
wrong (the filing is the authority) — it's that OUR extraction misread it: wrong
XBRL tag, a cumulative year-to-date value mistaken for a discrete quarter, or a
unit error. Every one of those leaves a fingerprint: the statements stop
cross-footing. So we verify each company's figures against *each other* and only
mark it publishable when its own numbers reconcile.

This is deterministic and needs no external source, so it runs every night and
gates the deploy. External cross-checking of the flagged movers against primary
sources (press releases, filing text) is the weekly human/Claude layer.

Worked example — Micron FY2026 $133.2B (+256%):
  real big move  -> discrete quarters SUM to the annual  -> reconciles -> PUBLISH
  cumulative bug -> YTD "quarters" sum to ~3x the annual -> fails      -> HOLD

Produces per company: verified (bool) + failed checks. Writes
data/audit/unverified.json for the weekly verification task to act on.

Usage:
  python -m pipeline.verify            # verify all, write unverified.json
  python -m pipeline.verify --ticker AAPL   # explain one company
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
COMP = DATA / "companies"
AUD = DATA / "audit"
AUD.mkdir(parents=True, exist_ok=True)

REL = 0.03   # 3% relative tolerance for reconciliation
REL_TTM = 0.01


def _close(a, b, rel=REL):
    if a is None or b is None:
        return None
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) / scale <= rel


def _latest(series, years, metric):
    s = series.get(metric, {})
    for y in reversed(years):
        if str(y) in s and s[str(y)] is not None:
            return s[str(y)], y
    return None, None


def verify_company(rec):
    """Return (verified, hard_checks, soft_checks).

    HARD checks are true invariants of correct extraction — if one fails, a
    number was definitely misread, so the company is held from publishing.
    SOFT checks are useful signals that legitimately fail on some accounting
    structures (non-controlling interests break assets=liab+equity; financial
    companies have no clean gross profit), so they are reported, not gating.
    """
    import re
    S = rec.get("series", {})
    years = rec.get("years", [])
    hard, soft = [], []

    # SOFT 1 — gross profit identity (fails for banks/insurers)
    gp, gy = _latest(S, years, "gross_profit")
    rv, ry = _latest(S, years, "revenue")
    cg, cy = _latest(S, years, "cost_of_revenue")
    if gp is not None and rv is not None and cg is not None and gy == ry == cy:
        soft.append(("gross_profit=rev-cogs", _close(gp, rv - cg), f"{gp:.3g} vs {rv-cg:.3g}"))

    # SOFT 2 — balance sheet identity (fails by the non-controlling-interest amount)
    at, ay = _latest(S, years, "assets")
    li, ly = _latest(S, years, "liabilities")
    eq, ey = _latest(S, years, "equity")
    if at is not None and li is not None and eq is not None and ay == ly == ey:
        soft.append(("assets=liab+equity", _close(at, li + eq), f"{at:.3g} vs {li+eq:.3g}"))

    # HARD 1 — quarterly revenues sum to annual (catches cumulative-vs-discrete)
    q = rec.get("q_series", {}).get("revenue", {})
    ql = rec.get("quarter_labels", [])
    ann_rev = S.get("revenue", {})
    fy_q = {}
    for lab in ql:
        m = re.match(r"FY(\d+) Q([1-4])", lab)
        if m and q.get(lab) is not None:
            fy_q.setdefault(int(m.group(1)), {})[int(m.group(2))] = q[lab]
    for fy2, qs in sorted(fy_q.items()):
        if len(qs) == 4:
            av = ann_rev.get(str(2000 + fy2))
            if av:
                qsum = sum(qs.values())
                hard.append((f"FY{fy2} quarters sum to annual", _close(qsum, av),
                             f"Σq {qsum:.3g} vs annual {av:.3g}"))
            break

    # HARD 2 — TTM equals sum of last 4 quarters (we compute it that way)
    ttm = rec.get("ttm", {})
    if ttm.get("revenue") is not None and len(ql) >= 4:
        last4 = [q.get(l) for l in ql[-4:]]
        if all(v is not None for v in last4):
            hard.append(("TTM rev = Σ last 4 quarters", _close(ttm["revenue"], sum(last4), REL_TTM),
                         f"{ttm['revenue']:.3g} vs {sum(last4):.3g}"))

    verified = not any(c[1] is False for c in hard)
    return verified, hard, soft


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", type=str, default="")
    args = ap.parse_args()

    if args.ticker:
        rec = json.loads((COMP / f"{args.ticker.replace('/','-')}.json").read_text())
        v, hard, soft = verify_company(rec)
        print(f"{args.ticker}: {'VERIFIED' if v else 'HELD (hard-check failed)'}")
        for name, ok, detail in hard:
            print(f"  HARD [{'ok ' if ok else 'FAIL'}] {name}: {detail}")
        for name, ok, detail in soft:
            print(f"  soft [{'ok ' if ok else 'flag'}] {name}: {detail}")
        return

    idx = json.loads((DATA / "index.json").read_text())
    held, soft_flags = [], []
    checked = 0
    for r in idx:
        p = COMP / f"{r['ticker'].replace('/','-')}.json"
        if not p.exists():
            continue
        rec = json.loads(p.read_text())
        v, hard, soft = verify_company(rec)
        if hard:
            checked += 1
        if not v:
            held.append({"ticker": r["ticker"], "name": r.get("name"),
                         "revenue": r.get("revenue"),
                         "failed": [c[0] for c in hard if c[1] is False]})
        sflag = [c[0] for c in soft if c[1] is False]
        if sflag:
            soft_flags.append({"ticker": r["ticker"], "flags": sflag})
    held.sort(key=lambda x: (x.get("revenue") or 0), reverse=True)
    (AUD / "unverified.json").write_text(json.dumps(held, indent=2))
    (AUD / "soft-flags.json").write_text(json.dumps(soft_flags, indent=2))
    print(f"hard-checked {checked} companies; {len(held)} HELD (failed a true "
          f"invariant — not published), {len(soft_flags)} soft-flagged (published).")
    for u in held[:20]:
        print(f"  HOLD {u['ticker']:7s} ${(u.get('revenue') or 0)/1e9:7.1f}B  {', '.join(u['failed'])}")


if __name__ == "__main__":
    main()
