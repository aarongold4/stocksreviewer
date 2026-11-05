#!/usr/bin/env python3
"""
run.py — build the company dataset.

Usage:
  python -m pipeline.run --limit 40            # demo subset (first N by market presence)
  python -m pipeline.run --tickers AAPL,MSFT   # specific tickers
  python -m pipeline.run --all                 # full universe (~10k; slow, use bulk cache)

Writes:
  data/companies/{TICKER}.json   full record per company
  data/index.json                compact screener index (one row per company)
"""
import argparse
import json
import sys
from pathlib import Path

from .edgar import get_companyfacts, get_submission_meta
from .normalize import build_record

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
COMPANIES = DATA / "companies"
COMPANIES.mkdir(parents=True, exist_ok=True)

# A curated, sector-diverse demo set so the sample site looks real.
DEMO = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B",
        "JPM", "BAC", "V", "MA", "WMT", "COST", "HD", "PG", "KO", "PEP",
        "JNJ", "PFE", "UNH", "MRK", "XOM", "CVX", "CAT", "DE", "BA", "GE",
        "DIS", "NFLX", "CRM", "ORCL", "ADBE", "INTC", "AMD", "QCOM",
        "T", "VZ", "F", "GM"]


def load_universe():
    tmap = json.loads((DATA / "company_tickers.json").read_text())
    # list of (ticker, cik, title), keep order (SEC sorts by size-ish)
    out = []
    for row in tmap.values():
        out.append((row["ticker"].upper(), int(row["cik_str"]), row["title"]))
    return out


def select(args, universe):
    by_ticker = {t: (t, c, n) for t, c, n in universe}
    if args.tickers:
        want = [x.strip().upper() for x in args.tickers.split(",")]
        return [by_ticker[t] for t in want if t in by_ticker]
    if args.all:
        return universe
    # demo subset: use curated DEMO list where present, else first N
    picked = [by_ticker[t] for t in DEMO if t in by_ticker]
    if args.limit and args.limit > len(picked):
        for row in universe:
            if row[0] not in {p[0] for p in picked}:
                picked.append(row)
            if len(picked) >= args.limit:
                break
    return picked[: args.limit] if args.limit else picked


def fmt_row(rec):
    m = rec["metrics"]
    rev = rec["series"].get("revenue", {})
    spark = [rev.get(str(y)) for y in rec["years"]]
    t = rec.get("ttm", {})
    return {
        "ticker": rec["ticker"],
        "name": rec["name"],
        "sector": rec["sector"],
        "industry": rec["industry"],
        "sic_desc": rec["sic_desc"],
        "fy": rec["latest"].get("fy"),
        "revenue": rec["latest"].get("revenue"),
        "net_income": rec["latest"].get("net_income"),
        "net_margin": m.get("net_margin"),
        "gross_margin": m.get("gross_margin"),
        "operating_margin": m.get("operating_margin"),
        "roe": m.get("roe"),
        "roa": m.get("roa"),
        "rev_cagr_5y": m.get("rev_cagr_5y"),
        "debt_to_equity": m.get("debt_to_equity"),
        "current_ratio": m.get("current_ratio"),
        "fcf": rec["latest"].get("fcf"),
        "fcf_margin": m.get("fcf_margin"),
        "eps": rec["latest"].get("eps_diluted"),
        "dcf": rec["dcf"]["intrinsic_per_share"] if rec.get("dcf") else None,
        "ttm_revenue": t.get("revenue"),
        "ttm_net_income": t.get("net_income"),
        "ttm_net_margin": t.get("net_margin"),
        "ttm_eps": t.get("eps_diluted"),
        "ttm_as_of": t.get("as_of"),
        "pays_dividend": m.get("pays_dividend"),
        "dividend_per_share": m.get("dividend_per_share"),
        "payout_ratio": m.get("payout_ratio"),
        "dividend_cagr_5y": m.get("dividend_cagr_5y"),
        "years": rec["years"],
        "rev_spark": spark,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--tickers", type=str, default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--with-sector", action="store_true", default=True)
    ap.add_argument("--cache-only-sector", action="store_true",
                    help="never fetch submissions over the network (use after fetch_bulk --subs)")
    args = ap.parse_args()

    universe = load_universe()
    targets = select(args, universe)
    print(f"Universe: {len(universe)} filers. Processing {len(targets)}.")

    index = []
    ok = skipped = 0
    for i, (ticker, cik, title) in enumerate(targets, 1):
        cf = get_companyfacts(cik)
        if not cf or "facts" not in cf:
            skipped += 1
            continue
        meta = get_submission_meta(cik, cache_only=args.cache_only_sector) if args.with_sector else {}
        try:
            rec = build_record(cf, ticker, meta)
        except Exception as e:
            print(f"  ! {ticker}: {e}", file=sys.stderr)
            skipped += 1
            continue
        rev_l = rec["latest"].get("revenue")
        if not rec["years"] or rev_l is None or rev_l < 0:
            skipped += 1
            continue
        safe = ticker.replace("/", "-")
        (COMPANIES / f"{safe}.json").write_text(json.dumps(rec))
        index.append(fmt_row(rec))
        ok += 1
        if i % 25 == 0 or i == len(targets):
            print(f"  {i}/{len(targets)} (ok={ok}, skipped={skipped})")

    index.sort(key=lambda r: (r["revenue"] or 0), reverse=True)
    (DATA / "index.json").write_text(json.dumps(index))
    print(f"Done. {ok} companies written, {skipped} skipped. Index: {len(index)} rows.")


if __name__ == "__main__":
    main()
