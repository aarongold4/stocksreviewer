#!/usr/bin/env python3
"""fetch_bulk_zip.py — download companyfacts.zip + submissions.zip (no extract)."""
import sys
import urllib.request
from pathlib import Path
from .edgar import USER_AGENT, CACHE

BULK = CACHE.parent / "bulk"
BULK.mkdir(parents=True, exist_ok=True)
URLS = {
    "companyfacts.zip": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
    "submissions.zip": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
}


def download(name, url):
    dest = BULK / name
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"  have {name} ({dest.stat().st_size/1e9:.2f} GB)")
        return
    print(f"  downloading {name} …", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=1200) as r, open(dest, "wb") as f:
        got = 0
        while True:
            chunk = r.read(1 << 22)
            if not chunk:
                break
            f.write(chunk); got += len(chunk)
    print(f"  saved {name} ({dest.stat().st_size/1e9:.2f} GB)", flush=True)


if __name__ == "__main__":
    which = sys.argv[1:] or list(URLS)
    for name in which:
        download(name, URLS[name])
