# StocksReviewer — stocksreviewer.com

Free company fundamentals for US public companies, sourced directly from SEC
EDGAR XBRL filings. Revenue, earnings, cash flow, balance sheet, margins,
returns, growth, and a transparent DCF — plus a fundamental screener and live
TradingView price charts. Pure static output for shared hosting.

## Why this design

EDGAR XBRL data is **public domain**, so it can be published freely. Commercial
data APIs (FMP, etc.) license you to *use* data privately but require a separate
paid agreement to *redistribute* it publicly. Building on EDGAR sidesteps that
entirely: the same primary source the paid vendors repackage, legal to publish,
$0 in data cost. Price charts come from TradingView's widget (its own license),
so no market-data redistribution issue either.

## Layout

```
pipeline/
  concepts.py     metric -> candidate XBRL tag fallback chains
  edgar.py        polite cached EDGAR client (User-Agent + <10 req/s)
  normalize.py    extract annual series, compute ratios/growth/DCF
  run.py          orchestrate: universe -> data/companies/*.json + data/index.json
  fetch_bulk.py   one-time bulk download for the full ~10k universe
data/
  company_tickers.json   SEC ticker->CIK map (committed)
  cache/                 per-CIK companyfacts + submission metadata (gitignore)
  companies/{TICKER}.json full record per company (build input)
  index.json             compact screener/search index
templates/  *.html (Jinja2)
static/     css/style.css, js/search.js, js/screener.js
build.py    render dist/
dist/       deployable static site
```

## Build (demo subset)

```bash
pip install -r requirements.txt
python -m pipeline.run --limit 40      # curated, sector-diverse sample
python build.py                        # render dist/
```

Other run modes:

```bash
python -m pipeline.run --tickers AAPL,MSFT,NVDA   # specific names
python -m pipeline.run --limit 500                # first 500 by SEC order
```

## Full universe (~10,000 filers)

Don't hammer the API 10k times. Use the bulk archives once, then build offline:

```bash
python -m pipeline.fetch_bulk --facts --subs       # downloads + extracts to cache/
python -m pipeline.run --all --cache-only-sector   # ZERO API calls; reads cache
python build.py
```

`fetch_bulk` pulls SEC's nightly `companyfacts.zip` (~1GB+) and `submissions.zip`
and lays them out in `data/cache/` exactly as the pipeline expects. Re-run it
when you want fresh filings (XBRL updates within ~a minute of dissemination).

## Refresh cadence

Fundamentals only change on new filings, so a weekly `fetch_bulk` + `run` + `build`
is plenty. Each stock page stamps its `data_through` date and links to the live
EDGAR record.

## Methodology notes (also on /methodology/)

- **Fiscal years** are labeled by the calendar year of the period-END date — the
  XBRL `fy` field is unreliable for comparative-year facts in later filings.
- **Tag fallbacks**: each metric resolves through ordered candidate tags; older
  tags backfill years a newer tag doesn't cover.
- **FCF** = operating cash flow − capex. **DCF** is a 2-stage model from latest
  FCF (growth clamped to the firm's revenue CAGR, 0–15%), terminal 2.5%,
  discount 10%; runs only when FCF and shares are positive.
- All server-side metrics are **price-independent**. Price-based ratios are left
  to the live TradingView chart rather than baked into the static page.
- Financials and foreign filers tag XBRL unusually — expect sparse/odd metrics
  for some; every page links to the source filing for verification.

## Deploy (Hostinger)

Upload the **contents** of `dist/` to `public_html/`. Trailing-slash URLs resolve
via each directory's `index.html`. No server-side code. Update `SITE` in
`build.py` (name/url) if the domain changes.

## Not investment advice

Informational only. See `/disclaimer/`.
