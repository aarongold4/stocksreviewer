"""
prices.py — compute price-performance % returns from adjusted closes.

Returns are *derived statistics* (percentages), not a redistributed price feed:
the pipeline fetches adjusted daily closes from a free source at build time,
computes trailing returns, and stores only the percentages + an "as of" date.
Prices themselves are never stored or served (the live chart is TradingView).

All 10 Fidelity-style periods: 5-day, 10-day (trading days), 1/3/6-month, YTD,
1/2/5/10-year (calendar, exact trailing date). Split- and dividend-adjusted.
"""
import bisect
import datetime as dt
import json
import time
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "data" / "prices"
CACHE.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (StocksReviewer research)"}
_last = [0.0]
DELAY = 0.3

PERIODS = ["5-day", "10-day", "1-month", "3-month", "6-month", "YTD",
           "1-year", "2-year", "5-year", "10-year"]


def _throttle():
    d = time.time() - _last[0]
    if d < DELAY:
        time.sleep(DELAY - d)
    _last[0] = time.time()


def _fetch_history(ticker):
    """[(date, adjclose)] sorted ascending, or None."""
    sym = ticker.upper()
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?range=11y&interval=1d&events=split")
    _throttle()
    try:
        req = urllib.request.Request(url, headers=UA)
        j = json.loads(urllib.request.urlopen(req, timeout=30).read())
        r = j["chart"]["result"][0]
        ts = r["timestamp"]
        adj = r["indicators"]["adjclose"][0]["adjclose"]
    except Exception:
        return None
    hist = [(dt.date.fromtimestamp(t), a) for t, a in zip(ts, adj) if a is not None]
    hist.sort()
    return hist or None


def _months_before(d, m):
    import calendar
    y, mo = d.year, d.month - m
    while mo <= 0:
        mo += 12; y -= 1
    return dt.date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))


def perf(ticker, force=False):
    cached = CACHE / f"{ticker.replace('/', '-')}.json"
    if cached.exists() and not force:
        try:
            return json.loads(cached.read_text())
        except Exception:
            pass
    hist = _fetch_history(ticker)
    if not hist or len(hist) < 6:
        return None
    dates = [d for d, _ in hist]
    px = [p for _, p in hist]
    last_d, last_p = hist[-1]

    def on_or_before(target):
        i = bisect.bisect_right(dates, target) - 1
        return px[i] if i >= 0 else None

    def r_trading(n):
        return (last_p / px[-1 - n] - 1) if len(px) > n else None

    def r_at(target):
        p = on_or_before(target)
        return (last_p / p - 1) if p else None

    out = {
        "5-day": r_trading(5),
        "10-day": r_trading(10),
        "1-month": r_at(_months_before(last_d, 1)),
        "3-month": r_at(_months_before(last_d, 3)),
        "6-month": r_at(_months_before(last_d, 6)),
        "YTD": r_at(dt.date(last_d.year - 1, 12, 31)),
        "1-year": r_at(_months_before(last_d, 12)),
        "2-year": r_at(_months_before(last_d, 24)),
        "5-year": r_at(_months_before(last_d, 60)),
        "10-year": r_at(_months_before(last_d, 120)),
    }
    out = {k: (round(v * 100, 2) if v is not None else None) for k, v in out.items()}
    out["as_of"] = last_d.isoformat()
    cached.write_text(json.dumps(out))
    return out
