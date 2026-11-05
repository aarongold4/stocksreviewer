"""
edgar.py — polite EDGAR client.

- Mandatory descriptive User-Agent (SEC requirement).
- Global rate limit < 10 req/sec (SEC throttle).
- On-disk cache so re-runs don't re-hit the API.

For full-universe (~10k) runs, prefer bulk files instead of per-CIK calls:
  https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip
  https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip
This client's get_companyfacts() reads from a local cache dir first, so you can
unzip the bulk archive into the cache and the rest of the pipeline is identical.
"""
import json
import time
import urllib.request
from pathlib import Path

USER_AGENT = "StocksReviewer data pipeline (contact@stocksreviewer.com)"
RATE_DELAY = 0.15  # ~6.6 req/s, safely under SEC's 10/s
CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

_last_call = [0.0]


def _throttle():
    dt = time.time() - _last_call[0]
    if dt < RATE_DELAY:
        time.sleep(RATE_DELAY - dt)
    _last_call[0] = time.time()


def _get_json(url: str) -> dict:
    _throttle()
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": url.split("/")[2],
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        return json.loads(raw)


def get_companyfacts(cik: int) -> dict | None:
    """Return companyfacts JSON for a CIK, using the on-disk cache."""
    cik10 = f"{int(cik):010d}"
    cached = CACHE / f"CIK{cik10}.json"
    if cached.exists():
        try:
            return json.loads(cached.read_text())
        except Exception:
            pass
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
    try:
        data = _get_json(url)
    except Exception:
        return None
    cached.write_text(json.dumps(data))
    return data


def get_submission_meta(cik: int, cache_only: bool = False) -> dict:
    """Lightweight company metadata (sector/SIC, exchange) from submissions API.
    With cache_only=True, never hits the network (used for full-universe runs
    after the bulk submissions archive has been extracted into the cache)."""
    cik10 = f"{int(cik):010d}"
    cached = CACHE / f"SUB{cik10}.json"
    if cached.exists():
        try:
            d = json.loads(cached.read_text())
            return d
        except Exception:
            pass
    if cache_only:
        return {}
    url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    try:
        d = _get_json(url)
    except Exception:
        return {}
    meta = {
        "sic_desc": d.get("sicDescription", ""),
        "sic": d.get("sic", ""),
        "exchange": (d.get("exchanges") or [""])[0],
        "fiscal_year_end": d.get("fiscalYearEnd", ""),
        "category": d.get("category", ""),
        "website": d.get("website", ""),
    }
    cached.write_text(json.dumps(meta))
    return meta
