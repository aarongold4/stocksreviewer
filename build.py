#!/usr/bin/env python3
"""
build.py — render the static site from data/companies/*.json + data/index.json.

Output -> dist/  (pure static; deploy contents to Hostinger public_html)
  /                      home + search
  /screener/             client-side fundamental screener
  /stocks/{TICKER}/      one page per company
  /about/ /methodology/ /data-sources/ /disclaimer/
  /search-index.json     ticker+name for the search box
  /screener-index.json   compact rows for the screener
  sitemap.xml, robots.txt
"""
import json, shutil
from datetime import date
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape, Undefined

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
SITE = {"name": "StocksReviewer", "url": "https://stocksreviewer.com",
        "tagline": "Company fundamentals, straight from SEC filings."}

EXCH = {"Nasdaq": "NASDAQ", "NasdaqGS": "NASDAQ", "NYSE": "NYSE",
        "NYSE Arca": "AMEX", "NYSEArca": "AMEX", "CBOE": "CBOE",
        "OTC": "OTC", "BATS": "BATS"}


def _none(v):
    return v is None or isinstance(v, Undefined)


# ---------- formatting ----------
def money(v, dp=1):
    if _none(v): return "—"
    a = abs(v); s = "-" if v < 0 else ""
    if a >= 1e12: return f"{s}${a/1e12:.{dp}f}T"
    if a >= 1e9:  return f"{s}${a/1e9:.{dp}f}B"
    if a >= 1e6:  return f"{s}${a/1e6:.{dp}f}M"
    if a >= 1e3:  return f"{s}${a/1e3:.{dp}f}K"
    return f"{s}${a:.0f}"

def num(v, dp=0):
    if _none(v): return "—"
    a = abs(v); s = "-" if v < 0 else ""
    if a >= 1e9: return f"{s}{a/1e9:.2f}B"
    if a >= 1e6: return f"{s}{a/1e6:.1f}M"
    return f"{s}{v:,.{dp}f}"

def pct(v, dp=1):
    if _none(v): return "—"
    return f"{v*100:.{dp}f}%"

def ratio(v, dp=2):
    if _none(v): return "—"
    return f"{v:.{dp}f}"

def usd(v, dp=2):
    if _none(v): return "—"
    return f"${v:,.{dp}f}"


def slugify(s):
    out = "".join(c.lower() if c.isalnum() else "-" for c in (s or ""))
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "other"


def sparkline(vals, w=104, h=26):
    """Tiny inline SVG sparkline from a list of values (None-tolerant)."""
    pts = [(i, v) for i, v in enumerate(vals) if v is not None]
    if len(pts) < 2:
        return ""
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    dx = (x1 - x0) or 1; dy = (y1 - y0) or 1
    coords = [(round((x - x0) / dx * (w - 2) + 1, 1),
               round(h - 1 - (y - y0) / dy * (h - 2), 1)) for x, y in pts]
    path = "M" + " L".join(f"{x},{y}" for x, y in coords)
    up = ys[-1] >= ys[0]
    col = "var(--green)" if up else "var(--red)"
    return (f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'preserveAspectRatio="none"><path d="{path}" fill="none" '
            f'stroke="{col}" stroke-width="1.5"/></svg>')


def chart_data(series, years):
    """List of bars with height % relative to max abs value."""
    vals = [(y, series.get(str(y))) for y in years]
    present = [v for _, v in vals if v is not None]
    if not present:
        return []
    mx = max(abs(v) for v in present) or 1
    out = []
    for y, v in vals:
        if v is None:
            out.append({"year": y, "val": None, "pct": 0, "neg": False})
        else:
            out.append({"year": y, "val": v, "pct": round(abs(v) / mx * 100, 1), "neg": v < 0})
    return out


def fmtval(v, kind):
    return usd(v) if kind == "usd" else money(v)


def _chart(pairs, fmt):
    """Axis-aware chart: bars positioned against a zero line, with scale."""
    present = [v for _, v in pairs if v is not None]
    if not present:
        return None
    mx, mn = max(present), min(present)
    hi, lo = max(mx, 0.0), min(mn, 0.0)
    rng = (hi - lo) or 1.0
    zero = hi / rng * 100  # % from top to the zero line
    bars = []
    for x, v in pairs:
        if v is None:
            bars.append({"x": x, "val": None, "h": 0, "neg": False, "top": zero})
        else:
            h = abs(v) / rng * 100
            top = (zero - h) if v >= 0 else zero
            bars.append({"x": x, "val": v, "h": round(h, 2), "neg": v < 0, "top": round(top, 2)})
    return {"bars": bars, "max": mx, "min": mn, "zero": round(zero, 2),
            "has_neg": mn < 0, "fmt": fmt}


def chart_data(series, years, fmt="money"):
    pairs = [(f"'{y % 100:02d}", series.get(str(y))) for y in years]
    return _chart(pairs, fmt)


def q_chart(qseries_metric, labels, fmt="money"):
    pairs = [(l[2:] if l.startswith("FY") else l, qseries_metric.get(l)) for l in labels]
    return _chart(pairs, fmt)


def stmt_rows(rec, keys):
    """Build statement table rows: [(label, [vals per year])]."""
    s = rec["series"]; years = rec["years"]
    rows = []
    for label, key in keys:
        ser = s.get(key, {})
        rows.append((label, [ser.get(str(y)) for y in years]))
    return rows


def main():
    index = json.loads((DATA / "index.json").read_text())
    prices = {}
    pf = DATA / "prices.json"
    if pf.exists():
        try:
            prices = json.loads(pf.read_text())
        except Exception:
            prices = {}
    companies = {}
    for p in (DATA / "companies").glob("*.json"):
        rec = json.loads(p.read_text())
        companies[rec["ticker"]] = rec

    # ---- verification gate: don't publish what can't be auto-verified ----
    # A company whose statements fail a true reconciliation invariant is HELD
    # out of the published site until a verification step clears it. Tickers in
    # data/verified_overrides.json (added after external verification, e.g. by
    # the weekly verification task) publish even if the auto-check can't confirm.
    from pipeline.verify import verify_company
    overrides = set()
    ov = DATA / "verified_overrides.json"
    if ov.exists():
        try:
            overrides = set(json.loads(ov.read_text()))
        except Exception:
            overrides = set()
    held = []
    for tk, rec in list(companies.items()):
        if tk in overrides:
            continue
        ok, _hard, _soft = verify_company(rec)
        if not ok:
            held.append(tk)
            del companies[tk]
    held_set = set(held)
    index = [r for r in index if r["ticker"] not in held_set]
    if held:
        print(f"verification: held {len(held)} unverified companies from publish "
              f"({', '.join(sorted(held)[:8])}{'…' if len(held) > 8 else ''})")
    (DATA / "audit").mkdir(exist_ok=True)
    (DATA / "audit" / "held-from-publish.json").write_text(json.dumps(sorted(held)))

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(ROOT / "static", DIST / "static")
    # publish audit artifacts so the weekly verification task can read them
    aud_src = DATA / "audit"
    if aud_src.exists():
        (DIST / "audit").mkdir(exist_ok=True)
        for f in aud_src.glob("*.json"):
            shutil.copy(f, DIST / "audit" / f.name)
        latest = sorted(aud_src.glob("report-*.md"))
        if latest:
            shutil.copy(latest[-1], DIST / "audit" / "latest-report.md")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters.update(money=money, num=num, pct=pct, ratio=ratio, usd=usd, spark=sparkline, fmtval=fmtval)

    today = date.today().isoformat()
    ctx = dict(site=SITE, year=date.today().year, today=today,
               total=len(index))

    def render(tpl, path, **kw):
        html = env.get_template(tpl).render(canonical=("/" if path == "" else f"/{path}/"), **ctx, **kw)
        d = DIST / path
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(html, encoding="utf-8")

    # search + screener indexes (client-side)
    search_idx = [{"t": r["ticker"], "n": r["name"]} for r in index]
    (DIST / "search-index.json").write_text(json.dumps(search_idx))
    (DIST / "screener-index.json").write_text(json.dumps(index))

    # sectors for filter
    sectors = sorted({r["sector"] for r in index if r.get("sector")})

    render("home.html", "", index=index, movers=index[:12])
    render("screener.html", "screener", sectors=sectors)
    render("compare.html", "compare")
    render("about.html", "about")
    render("methodology.html", "methodology")
    render("sources.html", "data-sources")
    render("disclaimer.html", "disclaimer")

    urls = ["/", "/screener/", "/compare/", "/about/", "/methodology/", "/data-sources/", "/disclaimer/"]

    # ---- programmatic "top" lists ----
    def has(k):
        return lambda r: r.get(k) is not None
    big = lambda r: (r.get("revenue") or 0) >= 1e8
    LISTS = [
        ("most-profitable", "Most Profitable Companies", "Ranked by latest annual net income.",
         "net_income", True, lambda r: (r.get("net_income") or -1) > 0, "money"),
        ("highest-net-margin", "Highest Net Margin", "Companies keeping the most of every revenue dollar.",
         "net_margin", True, lambda r: big(r) and r.get("net_margin") is not None, "pct"),
        ("highest-roe", "Highest Return on Equity", "Net income relative to shareholder equity.",
         "roe", True, lambda r: has("roe")(r) and big(r) and (r.get("roe") or 0) < 5, "pct"),
        ("fastest-growing", "Fastest-Growing Revenue", "Five-year revenue compound annual growth rate.",
         "rev_cagr_5y", True, lambda r: has("rev_cagr_5y")(r) and big(r), "pct"),
        ("highest-free-cash-flow", "Highest Free Cash Flow", "Operating cash flow minus capital expenditure.",
         "fcf", True, lambda r: (r.get("fcf") or 0) > 0, "money"),
        ("best-fcf-margin", "Best Free-Cash-Flow Margin", "Free cash flow as a share of revenue.",
         "fcf_margin", True, lambda r: big(r) and r.get("fcf_margin") is not None, "pct"),
        ("lowest-leverage", "Lowest Leverage (Debt/Equity)", "Profitable companies with the least debt relative to equity.",
         "debt_to_equity", False, lambda r: has("debt_to_equity")(r) and (r.get("debt_to_equity") or 0) >= 0 and (r.get("net_income") or -1) > 0, "ratio"),
        ("highest-ttm-revenue", "Highest Revenue (TTM)", "Trailing-twelve-month revenue — the freshest full-year figure.",
         "ttm_revenue", True, lambda r: r.get("ttm_revenue") is not None, "money"),
        ("most-profitable-ttm", "Most Profitable (TTM)", "Trailing-twelve-month net income.",
         "ttm_net_income", True, lambda r: (r.get("ttm_net_income") or -1) > 0, "money"),
        ("top-dividend-payers", "Top Dividend Payers", "Highest dividend per share (latest fiscal year).",
         "dividend_per_share", True, lambda r: r.get("pays_dividend") and r.get("dividend_per_share"), "usd"),
        ("best-dividend-growth", "Best Dividend Growth", "Five-year growth rate of dividend per share.",
         "dividend_cagr_5y", True, lambda r: has("dividend_cagr_5y")(r) and r.get("pays_dividend"), "pct"),
    ]
    list_meta = [(s, t) for s, t, *_ in LISTS]
    render("lists_hub.html", "lists", lists=list_meta)
    urls.append("/lists/")
    for slug, title, desc, key, desc_order, filt, vfmt in LISTS:
        rows = [r for r in index if filt(r)]
        rows.sort(key=lambda r: (r.get(key) is None, r.get(key) or 0), reverse=desc_order)
        render("list.html", f"lists/{slug}", list_title=title, list_desc=desc,
               rows=rows[:100], value_key=key, value_fmt=vfmt, lists=list_meta)
        urls.append(f"/lists/{slug}/")

    # ---- sector / sub-sector browse (GICS, Fidelity-style) ----
    by_sector = {}
    for r in index:
        sec = r.get("sector") or "Unclassified"
        ind = r.get("industry") or "Other"
        by_sector.setdefault(sec, {}).setdefault(ind, []).append(r)

    sector_cards = []
    for sec, inds in by_sector.items():
        sec_slug = slugify(sec)
        all_rows = [r for rows in inds.values() for r in rows]
        all_rows.sort(key=lambda r: (r.get("revenue") or 0), reverse=True)
        tot = sum(r.get("revenue") or 0 for r in all_rows)
        # industry summary for this sector
        ind_cards = []
        for ind, rows in inds.items():
            rows.sort(key=lambda r: (r.get("revenue") or 0), reverse=True)
            ind_slug = slugify(ind)
            ind_tot = sum(r.get("revenue") or 0 for r in rows)
            ind_cards.append({"industry": ind, "slug": ind_slug,
                              "count": len(rows), "total": ind_tot, "rows": rows})
            render("industry.html", f"sectors/{sec_slug}/{ind_slug}",
                   sector=sec, sector_slug=sec_slug, industry=ind, rows=rows)
            urls.append(f"/sectors/{sec_slug}/{ind_slug}/")
        ind_cards.sort(key=lambda c: c["total"], reverse=True)
        render("sector.html", f"sectors/{sec_slug}",
               sector=sec, industries=ind_cards, total_rows=len(all_rows), sec_total=tot)
        urls.append(f"/sectors/{sec_slug}/")
        sector_cards.append({"sector": sec, "slug": sec_slug,
                             "count": len(all_rows), "industries": len(inds), "total": tot})
    sector_cards.sort(key=lambda c: c["total"], reverse=True)
    render("sectors_hub.html", "sectors", sectors=sector_cards)
    urls.append("/sectors/")
    for tk, rec in companies.items():
        slug = tk.replace("/", "-")
        tvsym = f"{EXCH.get(rec.get('exchange',''), '')}:{tk.replace('-', '.')}".lstrip(":")
        render("stock.html", f"stocks/{slug}", rec=rec, tvsym=tvsym,
               perf=prices.get(tk),
               sector_slug=slugify(rec.get("sector") or "Unclassified"),
               rev_chart=chart_data(rec["series"].get("revenue", {}), rec["years"], "money"),
               ni_chart=chart_data(rec["series"].get("net_income", {}), rec["years"], "money"),
               fcf_chart=chart_data(rec["series"].get("fcf", {}), rec["years"], "money"),
               q_rev_chart=q_chart(rec.get("q_series", {}).get("revenue", {}), rec.get("quarter_labels", []), "money"),
               q_eps_chart=q_chart(rec.get("q_series", {}).get("eps_diluted", {}), rec.get("quarter_labels", []), "usd"),
               eps_chart=chart_data(rec["series"].get("eps_diluted", {}), rec["years"], "usd"),
               bvps_chart=chart_data(rec["series"].get("book_value_ps", {}), rec["years"], "usd"),
               fcfps_chart=chart_data(rec["series"].get("fcf_ps", {}), rec["years"], "usd"),
               dps_chart=chart_data(rec["series"].get("dividends_per_share", {}), rec["years"], "usd"),
               income_rows=stmt_rows(rec, [("Revenue","revenue"),("Cost of revenue","cost_of_revenue"),
                   ("Gross profit","gross_profit"),("Operating income","operating_income"),
                   ("Net income","net_income"),("Diluted EPS","eps_diluted")]),
               balance_rows=stmt_rows(rec, [("Total assets","assets"),("Current assets","current_assets"),
                   ("Total liabilities","liabilities"),("Current liabilities","current_liabilities"),
                   ("Cash & equivalents","cash"),("Shareholder equity","equity")]),
               cash_rows=stmt_rows(rec, [("Operating cash flow","op_cash_flow"),
                   ("Capital expenditure","capex"),("Free cash flow","fcf")]),
               eps_key="eps_diluted")
        urls.append(f"/stocks/{slug}/")

    # sitemap + robots
    entries = "\n".join(f"  <url><loc>{SITE['url']}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE['url']}/sitemap.xml\n")
    print(f"Built {len(urls)} pages ({len(companies)} stocks).")


if __name__ == "__main__":
    main()
