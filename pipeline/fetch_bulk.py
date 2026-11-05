#!/usr/bin/env python3
"""
fetch_bulk.py — populate the cache from SEC bulk archives.

For the full universe (~10k filers), downloading one companyfacts.json per CIK
over the API is slow and unkind to SEC's servers. SEC publishes nightly bulk
archives instead. This script downloads them once and extracts them into
data/cache/ in exactly the layout the pipeline already reads, so a subsequent
`python -m pipeline.run --all --cache-only-sector` makes ZERO API calls.

Archives (URLs occasionally change — see
https://www.sec.gov/search-filings/edgar-application-programming-interfaces):
  companyfacts.zip  ~1GB+  one CIK##########.json per filer (raw companyfacts)
  submissions.zip   large  filer submission histories (we keep sic/exchange)

Usage:
  python -m pipeline.fetch_bulk --facts            # fundamentals only
  python -m pipeline.fetch_bulk --facts --subs     # + sector/exchange metadata
"""
import argparse
import io
import json
import urllib.request
import zipfile
from pathlib import Path

from .edgar import USER_AGENT, CACHE

FACTS_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
SUBS_URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
BULK = CACHE.parent / "bulk"
BULK.mkdir(parents=True, exist_ok=True)


def download(url: str, dest: Path):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached: {dest.name} ({dest.stat().st_size/1e6:.0f} MB)")
        return
    print(f"  downloading {url} …")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    print(f"  saved {dest.name} ({dest.stat().st_size/1e6:.0f} MB)")


def extract_facts(zip_path: Path):
    """Each member CIK##########.json -> cache verbatim (pipeline reads it as-is)."""
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.startswith("CIK") or not name.endswith(".json"):
                continue
            (CACHE / Path(name).name).write_bytes(z.read(name))
            n += 1
            if n % 1000 == 0:
                print(f"    facts extracted: {n}")
    print(f"  facts extracted: {n}")


def extract_subs(zip_path: Path):
    """Keep only the trimmed metadata the pipeline needs, as SUB####.json."""
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            # main file per filer is CIK##########.json (skip the -submissions-NNN shards)
            base = Path(name).name
            if not base.startswith("CIK") or "-submissions-" in base or not base.endswith(".json"):
                continue
            try:
                d = json.loads(z.read(name))
            except Exception:
                continue
            cik10 = base[3:13]
            meta = {
                "sic_desc": d.get("sicDescription", ""),
                "sic": d.get("sic", ""),
                "exchange": (d.get("exchanges") or [""])[0],
                "fiscal_year_end": d.get("fiscalYearEnd", ""),
                "category": d.get("category", ""),
                "website": d.get("website", ""),
            }
            (CACHE / f"SUB{cik10}.json").write_text(json.dumps(meta))
            n += 1
            if n % 1000 == 0:
                print(f"    subs extracted: {n}")
    print(f"  subs extracted: {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", action="store_true", help="download+extract companyfacts.zip")
    ap.add_argument("--subs", action="store_true", help="download+extract submissions.zip")
    args = ap.parse_args()
    if not (args.facts or args.subs):
        ap.error("choose --facts and/or --subs")

    if args.facts:
        print("companyfacts:")
        fp = BULK / "companyfacts.zip"
        download(FACTS_URL, fp)
        extract_facts(fp)
    if args.subs:
        print("submissions:")
        sp = BULK / "submissions.zip"
        download(SUBS_URL, sp)
        extract_subs(sp)
    print("Done. Now run:  python -m pipeline.run --all --cache-only-sector")


if __name__ == "__main__":
    main()
