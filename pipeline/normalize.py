"""
normalize.py — turn raw companyfacts into a clean per-company record.

Output schema per company:
{
  "ticker", "name", "cik", "sic_desc", "exchange", "fiscal_year_end",
  "years": [2015, ..., 2024],          # fiscal years we have data for
  "series": { metric: {year: value} }, # annual time series, EDGAR-sourced
  "latest": { metric: value, "fy": int },
  "metrics": { computed ratios/growth for latest year },
  "dcf": { intrinsic value per share + assumptions } | None,
  "data_through": "YYYY-MM-DD"
}
All values are price-independent (EDGAR has no market data). Price-based ratios
(P/E, market cap) are intentionally left to the client/chart layer.
"""
from datetime import datetime
from .concepts import CONCEPTS, FLOW, INSTANT, PERSHARE, SHARES_TAGS, WEIGHTED_DILUTED_TAG
from .sic_gics import classify
from .names import display_name


def _days(start, end):
    try:
        a = datetime.fromisoformat(start)
        b = datetime.fromisoformat(end)
        return (b - a).days
    except Exception:
        return None


ANNUAL_FORMS = ("10-K", "10-K/A", "20-F", "40-F", "20-F/A")


def _fy_of(end):
    """Fiscal year label = calendar year of the period-end date.
    Matches company convention for both Sept-enders (Apple FY2021 ends 2021-09)
    and Jan-enders (Walmart FY2022 ends 2022-01)."""
    try:
        return int(end[:4])
    except Exception:
        return None



# ---------------------------------------------------------------------------
# Fiscal-calendar changes (FY-end moves and reverse mergers).
# When a filer's fiscal calendar changes, its companyfacts mix periods from two
# calendars: e.g. Ferguson (July FY -> calendar), or a reverse merger where the
# accounting acquirer's history replaces the old registrant's (Republic into
# Mesa's CIK; Hulu + Live TV into fuboTV's). Keyed by period-end year alone,
# those periods collide. build_record() detects the change and sets _CAL; it is
# None for every other company, so their extraction is unchanged.
_CAL = None


def _month_near(m, target, tol=1):
    d = abs(m - target) % 12
    return min(d, 12 - d) <= tol


def _annual_periods(facts, tags):
    """{fy: (start, end)} of 12-month annual periods, newest filing per year."""
    out, seen = {}, {}
    for t in tags:
        rows = (facts.get(t) or {}).get("units", {}).get("USD") or []
        for r in rows:
            if r.get("form") not in ANNUAL_FORMS:
                continue
            d = _days(r.get("start"), r.get("end"))
            if d is None or not (350 <= d <= 380):
                continue
            fy = _fy_of(r.get("end", ""))
            if fy is None:
                continue
            filed = r.get("filed", "")
            if fy in seen and filed <= seen[fy]:
                continue
            seen[fy] = filed
            out[fy] = (r["start"], r["end"])
    return out


def _calendar_context(gaap, rev_tags, meta_fye_month):
    """Return a context dict if the fiscal calendar changed, else None."""
    per = _annual_periods(gaap, rev_tags)
    if not per:
        return None
    by_end = sorted(per.items(), key=lambda kv: kv[1][1], reverse=True)
    last_fy, (last_start, last_end) = by_end[0]
    last_m = int(last_end[5:7])
    annual_change = any(not _month_near(int(e[5:7]), last_m) for _s, e in per.values())
    meta_change = not _month_near(meta_fye_month, last_m)
    if not (annual_change or meta_change):
        return None
    kept = {}
    for fy, (st, en) in by_end:          # most recent unbroken run on the current calendar
        if not _month_near(int(en[5:7]), last_m):
            break
        kept[fy] = (st, en)
    return {
        "annual_change": annual_change,
        "last_m": last_m,
        "kept": kept,
        "first_kept_end": min(e for _s, e in kept.values()),
        "last_fy": last_fy,
        "last_end": last_end,
        "ends": {},
    }


def _annual_row_ok(r):
    """Under a calendar change, drop annual/instant rows from the old calendar."""
    if not _CAL or not _CAL["annual_change"]:
        return True
    end = r.get("end", "")
    try:
        m = int(end[5:7])
    except Exception:
        return False
    if not _month_near(m, _CAL["last_m"]):
        return False
    d = _days(end, _CAL["first_kept_end"])
    return d is None or d <= 5


def _quarter_key_cal(r, fye_month):
    """(fy, q) for a discrete 10-Q quarter under a calendar change, or None to drop.

    A quarter inside one of the current calendar's fiscal years takes that
    year's label, and its position must match the filing's own fiscal period
    (fp): a 10-Q never reports a fiscal Q4, and an old-calendar quarter lands
    in the wrong position. A quarter after the last annual period belongs to
    the new calendar (meta fiscal-year end) and must start a later fiscal year.
    Anything else (old-calendar history, transition periods) is dropped.
    """
    start, end, fp = r.get("start", ""), r.get("end", ""), r.get("fp")
    for fy, (a_start, a_end) in _CAL["kept"].items():
        d_s = _days(a_start, start)
        d_e = _days(end, a_end)
        if d_s is None or d_e is None or d_s < -5 or d_e < -5:
            continue
        pos = min(4, max(1, round(_days(a_start, end) / 91.31)))
        if pos == 4:
            return None
        if fp in ("Q1", "Q2", "Q3", "Q4") and fp != f"Q{pos}":
            return None
        return (fy, pos)
    if end > _CAL["last_end"]:
        k = _quarter_of(end, fye_month)
        if not k or k[0] <= _CAL["last_fy"]:
            return None
        if fp in ("Q1", "Q2", "Q3", "Q4") and fp != f"Q{k[1]}":
            return None
        return k
    return None


def _annual_from_tag(facts, tag, unit, kind):
    """Return {fiscal_year: value} for one tag, annual figures only.
    Keyed by period-END year (the `fy`/`fp` fields are unreliable for
    comparative-year facts pulled from later filings)."""
    node = facts.get(tag)
    if not node:
        return {}
    rows = node.get("units", {}).get(unit)
    if not rows:
        return {}
    out, seen_filed = {}, {}
    for r in rows:
        if r.get("form") not in ANNUAL_FORMS:
            continue
        if not _annual_row_ok(r):
            continue
        if kind in (FLOW, PERSHARE):
            d = _days(r.get("start"), r.get("end"))
            if d is None or not (350 <= d <= 380):
                continue
        fy = _fy_of(r.get("end", ""))
        if fy is None:
            continue
        filed = r.get("filed", "")
        # dedupe by fiscal year; keep most recently filed (restatements win)
        if fy in seen_filed and filed <= seen_filed[fy]:
            continue
        seen_filed[fy] = filed
        out[fy] = r["val"]
    return out


def _extract(facts, kind, unit, candidates):
    """Try candidate tags in order; merge so older tags backfill missing years."""
    merged = {}
    for tag in candidates:
        series = _annual_from_tag(facts, tag, unit, kind)
        for fy, v in series.items():
            merged.setdefault(fy, v)  # earlier (higher-priority) tags win
    return merged


# Revenue is special. Many filers (REITs, airlines, banks, insurers, utilities)
# tag BOTH RevenueFromContractWithCustomerExcludingAssessedTax (the ASC 606
# contract-revenue subset) and Revenues (total revenue, which also counts lease,
# interest, insurance and other income). Taking the first tag in priority order
# showed the subset as "revenue". Instead, for each fiscal year take the LARGEST
# value among the total-revenue tags. The gross-of-excise tag
# (…IncludingAssessedTax) is NOT in the max — it would inflate revenue for
# excise-heavy filers — and only backfills years no other tag covers.
REVENUE_MAX_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
)


def _extract_revenue(facts, unit, candidates):
    """({fy: value}, {fy: winning_tag}) — largest total-revenue tag per year."""
    per_tag = {t: _annual_from_tag(facts, t, unit, FLOW) for t in candidates}
    merged, tags = {}, {}
    for tag in candidates:
        if tag not in REVENUE_MAX_TAGS:
            continue
        for fy, v in per_tag[tag].items():
            if v is None:
                continue
            if fy not in merged or v > merged[fy]:
                merged[fy], tags[fy] = v, tag
    for tag in candidates:          # fallback-only tags backfill missing years
        if tag in REVENUE_MAX_TAGS:
            continue
        for fy, v in per_tag[tag].items():
            if fy not in merged and v is not None:
                merged[fy], tags[fy] = v, tag
    return merged, tags


def _shares_series(allfacts):
    """Shares outstanding by fiscal year, from dei/us-gaap instant tags."""
    for tax, tag in SHARES_TAGS:
        facts = allfacts.get(tax, {})
        node = facts.get(tag)
        if not node:
            continue
        rows = node.get("units", {}).get("shares")
        if not rows:
            continue
        out, seen = {}, {}
        for r in rows:
            if r.get("form") not in ANNUAL_FORMS or not _annual_row_ok(r):
                continue
            fy = _fy_of(r.get("end", ""))
            if fy is None:
                continue
            filed = r.get("filed", "")
            if fy in seen and filed <= seen[fy]:
                continue
            seen[fy] = filed
            out[fy] = r["val"]
        if out:
            return out
    # fallback: weighted diluted (flow)
    tax, tag = WEIGHTED_DILUTED_TAG
    node = allfacts.get(tax, {}).get(tag)
    if node:
        rows = node.get("units", {}).get("shares", [])
        out, seen = {}, {}
        for r in rows:
            if r.get("form") not in ANNUAL_FORMS or not _annual_row_ok(r):
                continue
            d = _days(r.get("start"), r.get("end"))
            if d is not None and not (350 <= d <= 380):
                continue
            fy = _fy_of(r.get("end", ""))
            if fy is None:
                continue
            filed = r.get("filed", "")
            if fy in seen and filed <= seen[fy]:
                continue
            seen[fy] = filed
            out[fy] = r["val"]
        return out
    return {}


def _quarter_of(end, fye_month=12):
    """(fiscal_year, fiscal_quarter 1-4) from a period-end date and the
    company's fiscal-year-end month. Handles non-calendar fiscal years
    (e.g. Apple's September year-end) without calendar-quarter collisions."""
    try:
        y = int(end[:4]); m = int(end[5:7])
    except Exception:
        return None
    fy = y if m <= fye_month else y + 1
    q = ((m - fye_month - 1) % 12) // 3 + 1
    return (fy, q)


def _quarterly_flow(facts, candidates, fye_month):
    """{(fiscal_year, q): value} from discrete ~90-day quarterly periods (10-Q)."""
    merged, seen = {}, {}
    for tag in candidates:
        node = facts.get(tag)
        if not node:
            continue
        rows = node.get("units", {}).get("USD") or node.get("units", {}).get("USD/shares")
        if not rows:
            continue
        for r in rows:
            if r.get("form") not in ("10-Q", "10-Q/A"):
                continue
            d = _days(r.get("start"), r.get("end"))
            if d is None or not (80 <= d <= 100):
                continue
            if _CAL:
                key = _quarter_key_cal(r, fye_month)
            else:
                key = _quarter_of(r.get("end", ""), fye_month)
            if not key:
                continue
            if _CAL:
                _CAL["ends"].setdefault(key, r.get("end", ""))
            filed = r.get("filed", "")
            if key in seen and filed <= seen[key]:
                continue
            seen[key] = filed
            merged[key] = r["val"]
    return merged


def _quarterly_revenue(facts, candidates, fye_month, annual_tags):
    """Quarterly revenue that does not mix tags within a fiscal year.

    Each tag gives its own discrete quarters (newest filing of that tag wins).
    For each fiscal year, use the tag that supplied that year's annual figure
    when it covers Q1-Q3 (so Q4 = annual - Q1..Q3 stays consistent). Otherwise
    take, per quarter, the largest value among the total-revenue tags, falling
    back to the excise-inclusive tag only where nothing else covers a quarter.
    """
    per_tag = {t: _quarterly_flow(facts, [t], fye_month) for t in candidates}
    years = {y for qs in per_tag.values() for (y, _q) in qs}
    out = {}
    for y in years:
        win = annual_tags.get(y)
        if win and all((y, q) in per_tag.get(win, {}) for q in (1, 2, 3)):
            for q in (1, 2, 3, 4):
                if (y, q) in per_tag[win]:
                    out[(y, q)] = per_tag[win][(y, q)]
            continue
        for q in (1, 2, 3, 4):
            best = None
            for t in candidates:
                if t not in REVENUE_MAX_TAGS:
                    continue
                v = per_tag[t].get((y, q))
                if v is not None and (best is None or v > best):
                    best = v
            if best is None:
                for t in candidates:
                    v = per_tag[t].get((y, q))
                    if v is not None:
                        best = v
                        break
            if best is not None:
                out[(y, q)] = best
    return out


def _build_quarters(gaap, annual, fye_month, revenue_tags=None):
    """Return (quarter_labels, q_series, ttm) for income-statement metrics,
    deriving Q4 = annual − (Q1+Q2+Q3) where possible."""
    metrics = {
        "revenue": CONCEPTS["revenue"][2],
        "net_income": CONCEPTS["net_income"][2],
        "eps_diluted": CONCEPTS["eps_diluted"][2],
    }
    q_raw = {m: _quarterly_flow(gaap, cands, fye_month) for m, cands in metrics.items()}
    q_raw["revenue"] = _quarterly_revenue(gaap, metrics["revenue"], fye_month,
                                          revenue_tags or {})

    if _CAL:
        # A closed fiscal year shows quarters only if Q1-Q3 all came from the
        # current calendar; a lone surviving quarter would be misleading.
        for m, qs in q_raw.items():
            for y in {y for (y, _q) in qs}:
                if y <= _CAL["last_fy"] and not all((y, q) in qs for q in (1, 2, 3)):
                    for q in (1, 2, 3, 4):
                        qs.pop((y, q), None)

    for m, qs in q_raw.items():
        ann = annual.get(m, {})
        years = {y for (y, q) in qs}
        for y in years:
            if (y, 4) in qs:
                continue
            if all((y, q) in qs for q in (1, 2, 3)) and y in ann and ann[y] is not None:
                partial = qs[(y, 1)] + qs[(y, 2)] + qs[(y, 3)]
                qs[(y, 4)] = round(ann[y] - partial, 4)

    keys = sorted(set().union(*[set(qs) for qs in q_raw.values()])) if any(q_raw.values()) else []
    keys = keys[-12:]
    labels = [f"FY{y % 100:02d} Q{q}" for (y, q) in keys]
    q_series = {m: {f"FY{y % 100:02d} Q{q}": qs.get((y, q)) for (y, q) in keys} for m, qs in q_raw.items()}

    ttm = {}
    last4 = keys[-4:]
    if _CAL and len(last4) == 4:
        # TTM only when the last four quarters are consecutive (no transition gap)
        ends = []
        for (y, q) in last4:
            e = _CAL["ends"].get((y, q))
            if e is None and q == 4 and y in _CAL["kept"]:
                e = _CAL["kept"][y][1]
            ends.append(e)
        gaps = [_days(a, b) if a and b else None for a, b in zip(ends, ends[1:])]
        if any(g is None or not (75 <= g <= 105) for g in gaps):
            last4 = []
    if len(last4) == 4:
        for m, qs in q_raw.items():
            vals = [qs.get(k) for k in last4]
            ttm[m] = round(sum(vals), 4) if all(v is not None for v in vals) else None
        ttm["as_of"] = labels[-1]
    return labels, q_series, ttm


def _safe_div(a, b):
    try:
        if a is None or b in (None, 0):
            return None
        return a / b
    except Exception:
        return None


def _cagr(series, years_back):
    yrs = sorted(series)
    if len(yrs) < years_back + 1:
        return None
    last, first = series[yrs[-1]], series[yrs[-1 - years_back]]
    if first is None or last is None or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1 / years_back) - 1


def build_record(companyfacts, ticker, meta):
    global _CAL
    allfacts = companyfacts.get("facts", {})
    gaap = allfacts.get("us-gaap", {})
    _CAL = _calendar_context(gaap, CONCEPTS["revenue"][2], _fye_month(meta))
    try:
        rec = _build_record(companyfacts, ticker, meta, allfacts, gaap)
    finally:
        _CAL = None
    return rec


def _fye_month(meta):
    fye = meta.get("fiscal_year_end", "") or ""
    try:
        m = int(fye[:2]) if len(fye) >= 2 else 12
        return m if 1 <= m <= 12 else 12
    except Exception:
        return 12


def _build_record(companyfacts, ticker, meta, allfacts, gaap):

    series = {}
    revenue_tags = {}
    for name, (kind, unit, cands) in CONCEPTS.items():
        if name == "revenue":
            s, revenue_tags = _extract_revenue(gaap, unit, cands)
        else:
            s = _extract(gaap, kind, unit, cands)
        if s:
            series[name] = s
    shares = _shares_series(allfacts)
    if shares:
        series["shares"] = shares

    # derived per-year: gross profit (if absent but revenue & cogs present), fcf, margins
    rev = series.get("revenue", {})
    cogs = series.get("cost_of_revenue", {})
    if "gross_profit" not in series and rev and cogs:
        series["gross_profit"] = {y: rev[y] - cogs[y] for y in rev if y in cogs}
    ocf = series.get("op_cash_flow", {})
    capex = series.get("capex", {})
    if ocf:
        series["fcf"] = {y: ocf[y] - capex.get(y, 0) for y in ocf}

    # derived per-share series (for trend charts) — computed, not filed
    sh = series.get("shares", {})
    if sh:
        eq = series.get("equity", {})
        fcf_s = series.get("fcf", {})
        rev_s = series.get("revenue", {})
        series["book_value_ps"] = {y: eq[y] / sh[y] for y in eq if y in sh and sh[y]}
        series["fcf_ps"] = {y: fcf_s[y] / sh[y] for y in fcf_s if y in sh and sh[y]}
        series["revenue_ps"] = {y: rev_s[y] / sh[y] for y in rev_s if y in sh and sh[y]}

    years = sorted(set().union(*[set(s) for s in series.values()])) if series else []
    # Anchor the latest fiscal year to core flows (revenue, then net income);
    # cover-page shares facts are dated at filing time and can create a phantom
    # year beyond the last reported fiscal year.
    anchor = None
    for key in ("revenue", "net_income"):
        if series.get(key):
            anchor = max(series[key])
            break
    if anchor is not None:
        years = [y for y in years if y <= anchor]
    # keep last 12 fiscal years
    years = years[-12:]

    def latest(metric):
        s = series.get(metric, {})
        ys = [y for y in years if y in s]
        return s[ys[-1]] if ys else None

    fy = years[-1] if years else None
    L = {m: latest(m) for m in series}
    L_fy = fy

    # ---- metrics (latest year, price-independent) ----
    rev_l = latest("revenue")
    ni_l = latest("net_income")
    eq_l = latest("equity")
    assets_l = latest("assets")
    gp_l = latest("gross_profit")
    oi_l = latest("operating_income")
    fcf_l = latest("fcf")
    shares_l = latest("shares")
    debt_l = (latest("long_term_debt") or 0) + (latest("short_term_debt") or 0)

    # dividends
    dps_l = latest("dividends_per_share")
    divpaid_l = latest("dividends_paid")
    divpaid_abs = abs(divpaid_l) if divpaid_l is not None else None
    eps_l = latest("eps_diluted")
    payout = None
    if divpaid_abs is not None and ni_l and ni_l > 0:
        payout = divpaid_abs / ni_l
    elif dps_l and eps_l and eps_l > 0:
        payout = dps_l / eps_l
    pays_dividend = bool((dps_l and dps_l > 0) or (divpaid_abs and divpaid_abs > 0))
    dps_pos = {y: v for y, v in series.get("dividends_per_share", {}).items() if v and v > 0}

    metrics = {
        "gross_margin": _safe_div(gp_l, rev_l),
        "operating_margin": _safe_div(oi_l, rev_l),
        "net_margin": _safe_div(ni_l, rev_l),
        "roe": _safe_div(ni_l, eq_l),
        "roa": _safe_div(ni_l, assets_l),
        "debt_to_equity": _safe_div(debt_l, eq_l) if eq_l and eq_l > 0 else None,
        "current_ratio": _safe_div(latest("current_assets"), latest("current_liabilities")),
        "fcf_margin": _safe_div(fcf_l, rev_l),
        "book_value_per_share": _safe_div(eq_l, shares_l),
        "fcf_per_share": _safe_div(fcf_l, shares_l),
        "revenue_per_share": _safe_div(rev_l, shares_l),
        "rev_cagr_3y": _cagr(rev, 3),
        "rev_cagr_5y": _cagr(rev, 5),
        "ni_cagr_3y": _cagr({y: v for y, v in series.get("net_income", {}).items() if v and v > 0}, 3),
        "total_debt": debt_l or None,
        "dividend_per_share": dps_l,
        "payout_ratio": payout,
        "pays_dividend": pays_dividend,
        "dividend_cagr_5y": _cagr(dps_pos, 5),
        "dividends_paid": divpaid_abs,
    }

    dcf = _simple_dcf(series.get("fcf", {}), shares_l, metrics.get("rev_cagr_5y"))
    sector, industry = classify(meta.get("sic", ""), ticker)

    fye = meta.get("fiscal_year_end", "") or ""
    try:
        fye_month = int(fye[:2]) if len(fye) >= 2 else 12
        if not (1 <= fye_month <= 12):
            fye_month = 12
    except Exception:
        fye_month = 12
    q_labels, q_series, ttm = _build_quarters(gaap, series, fye_month, revenue_tags)
    if ttm.get("revenue") and ttm.get("net_income") is not None:
        ttm["net_margin"] = _safe_div(ttm["net_income"], ttm["revenue"])

    return {
        "ticker": ticker,
        "name": display_name(ticker, companyfacts.get("entityName", ticker)),
        "cik": companyfacts.get("cik"),
        "sic_desc": meta.get("sic_desc", ""),
        "sector": sector,
        "industry": industry,
        "exchange": meta.get("exchange", ""),
        "fiscal_year_end": meta.get("fiscal_year_end", ""),
        "years": years,
        "series": {m: {str(y): s.get(y) for y in years if y in s} for m, s in series.items()},
        "latest": {**L, "fy": L_fy},
        "metrics": metrics,
        "dcf": dcf,
        "quarter_labels": q_labels,
        "q_series": q_series,
        "ttm": ttm,
        "revenue_tag": revenue_tags.get(fy) if fy is not None else None,
        "calendar_change": bool(_CAL),
        "data_through": datetime.utcnow().strftime("%Y-%m-%d"),
    }


def _simple_dcf(fcf_series, shares, growth_hint):
    """A transparent 2-stage DCF -> intrinsic value per share.
    Conservative defaults; only runs when latest FCF and shares are positive."""
    ys = sorted(fcf_series)
    if not ys or not shares or shares <= 0:
        return None
    fcf0 = fcf_series[ys[-1]]
    if fcf0 is None or fcf0 <= 0:
        return None
    # growth: clamp the 5y revenue CAGR hint into a sane band
    g = growth_hint if growth_hint is not None else 0.06
    g = max(0.0, min(g, 0.15))
    r = 0.10        # discount rate
    tg = 0.025      # terminal growth
    years = 5
    pv = 0.0
    fcf = fcf0
    for t in range(1, years + 1):
        fcf *= (1 + g)
        pv += fcf / ((1 + r) ** t)
    terminal = fcf * (1 + tg) / (r - tg)
    pv += terminal / ((1 + r) ** years)
    return {
        "intrinsic_per_share": round(pv / shares, 2),
        "assumptions": {"growth_5y": round(g, 4), "discount_rate": r,
                        "terminal_growth": tg, "base_fcf": fcf0},
    }
