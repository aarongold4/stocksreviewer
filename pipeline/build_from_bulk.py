#!/usr/bin/env python3
"""
build_from_bulk.py — process the FULL ticker universe (~10k) from the SEC bulk
zips WITHOUT extracting them (the uncompressed set is too big for most disks).

It opens companyfacts.zip + submissions.zip, walks the ticker->CIK map, reads
each company's member directly from the zip, normalizes, and writes the slim
per-company record + index row. Resumable: companies already written are skipped.

Steps:
  1. python -m pipeline.fetch_bulk_zip         # download the two zips (~2.9GB)
  2. python -m pipeline.build_from_bulk        # stream-process into data/
  3. python build.py                           # render the site

Tune --limit to cap how many to process (default: all).
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

from .normalize import build_record
from .edgar import CACHE

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
COMPANIES = DATA / "companies"
BULK = CACHE.parent / "bulk"
FACTS_ZIP = BULK / "companyfacts.zip"
SUBS_ZIP = BULK / "submissions.zip"


# Predecessor-CIK fallbacks: a ticker whose current SEC-map CIK is a freshly
# reincorporated holding company with no annual 10-K yet, pointed at the
# predecessor filer that still carries the full financial history. Revisit when
# the new entity files its first annual report.
CIK_OVERRIDE = {
    "XOM": 34088,  # ExxonMobil: 2026 reincorporation under new holdco CIK 2115436
}


def load_universe():
    tmap = json.loads((DATA / "company_tickers.json").read_text())
    out = []
    for r in tmap.values():
        tk = r["ticker"].upper()
        cik = CIK_OVERRIDE.get(tk, int(r["cik_str"]))
        out.append((tk, cik, r["title"]))
    return out


def sub_meta_from_zip(zf, cik10):
    try:
        d = json.loads(zf.read(f"CIK{cik10}.json"))
    except Exception:
        return {}
    return {
        "sic_desc": d.get("sicDescription", ""),
        "sic": d.get("sic", ""),
        "exchange": (d.get("exchanges") or [""])[0],
        "fiscal_year_end": d.get("fiscalYearEnd", ""),
    }


def fmt_row(rec):
    from .run import fmt_row as _f
    return _f(rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--resume", action="store_true", default=True)
    args = ap.parse_args()

    if not FACTS_ZIP.exists():
        sys.exit("Missing companyfacts.zip — run: python -m pipeline.fetch_bulk_zip")
    COMPANIES.mkdir(parents=True, exist_ok=True)

    universe = load_universe()
    if args.limit:
        universe = universe[: args.limit]

    facts_zip = zipfile.ZipFile(FACTS_ZIP)
    facts_names = set(facts_zip.namelist())
    subs_zip = zipfile.ZipFile(SUBS_ZIP) if SUBS_ZIP.exists() else None

    index = []
    ok = skipped = 0
    for i, (ticker, cik, title) in enumerate(universe, 1):
        safe = ticker.replace("/", "-")
        out = COMPANIES / f"{safe}.json"
        if out.exists():
            try:
                index.append(fmt_row(json.loads(out.read_text())))
                ok += 1
                continue
            except Exception:
                pass
        cik10 = f"{cik:010d}"
        member = f"CIK{cik10}.json"
        if member not in facts_names:
            skipped += 1
            continue
        try:
            cf = json.loads(facts_zip.read(member))
        except Exception:
            skipped += 1
            continue
        meta = sub_meta_from_zip(subs_zip, cik10) if subs_zip else {}
        try:
            rec = build_record(cf, ticker, meta)
        except Exception:
            skipped += 1
            continue
        rev_l = rec["latest"].get("revenue")
        if not rec["years"] or rev_l is None or rev_l < 0:
            skipped += 1
            continue
        out.write_text(json.dumps(rec))
        index.append(fmt_row(rec))
        ok += 1
        if i % 500 == 0:
            print(f"  {i}/{len(universe)} (ok={ok}, skipped={skipped})", flush=True)

    index.sort(key=lambda r: (r["revenue"] or 0), reverse=True)
    (DATA / "index.json").write_text(json.dumps(index))
    print(f"Done. {ok} companies, {skipped} skipped. Index {len(index)} rows.")


if __name__ == "__main__":
    main()
