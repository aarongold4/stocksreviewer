#!/usr/bin/env python3
"""
fetch_prices.py — compute price performance for companies in the index.

  python -m pipeline.fetch_prices --limit 50      # top 50 by revenue
  python -m pipeline.fetch_prices --tickers AAPL,NVDA,TSLA
  python -m pipeline.fetch_prices --all           # everything in the index

Writes data/prices.json (ticker -> {period: pct, as_of}). Resumable via the
per-ticker cache in data/prices/. Run as part of the refresh job; price
performance is "as of" the last run, stamped on each stock page.
"""
import argparse
import json
import sys
from pathlib import Path
from .prices import perf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--tickers", type=str, default="")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    index = json.loads((DATA / "index.json").read_text())
    if args.tickers:
        want = {t.strip().upper() for t in args.tickers.split(",")}
        tickers = [r["ticker"] for r in index if r["ticker"] in want]
    elif args.all:
        tickers = [r["ticker"] for r in index]
    else:
        tickers = [r["ticker"] for r in index[: args.limit]]

    # merge with existing
    pf_path = DATA / "prices.json"
    out = {}
    if pf_path.exists():
        try:
            out = json.loads(pf_path.read_text())
        except Exception:
            out = {}

    ok = fail = 0
    for i, tk in enumerate(tickers, 1):
        p = perf(tk)
        if p:
            out[tk] = p; ok += 1
        else:
            fail += 1
        if i % 50 == 0:
            print(f"  {i}/{len(tickers)} (ok={ok}, fail={fail})", flush=True)
            pf_path.write_text(json.dumps(out))
    pf_path.write_text(json.dumps(out))
    print(f"Done. {ok} priced, {fail} failed. {len(out)} total in prices.json.")


if __name__ == "__main__":
    main()
