#!/usr/bin/env python3
"""
revenue_preview.py — show what the revenue-tag fix changes, WITHOUT writing
data/companies or touching the site.

For every company in data/index.json it rebuilds the record from the SEC bulk
companyfacts.zip twice, on the same fresh data:
  old rule: first revenue tag in priority order wins (previous behaviour)
  new rule: largest total-revenue tag per period (pipeline/normalize.py)
so the difference is the rule alone, not new filings. It also compares the
old-rule rebuild with the committed record, to show how stale committed
fundamentals are.

Writes data/audit/revenue-preview.md and data/audit/revenue-preview.json.

  python -m pipeline.fetch_bulk_zip
  python -m pipeline.revenue_preview
"""
import json
import zipfile
from pathlib import Path

from . import normalize as N
from .build_from_bulk import FACTS_ZIP, SUBS_ZIP, sub_meta_from_zip, CIK_OVERRIDE
from .verify import verify_company

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
COMP = DATA / "companies"
AUD = DATA / "audit"

TEST_SET = ["RJET", "AHRT", "AHRT-PA", "MAGN", "RCAT", "MEGR", "FSTJ"]
CANARIES = ["AAPL", "MSFT", "JPM", "O", "DAL", "DUK"]
THRESH = 0.05


def _old_extract_revenue(facts, unit, candidates):
    s = N._extract(facts, N.FLOW, unit, candidates)
    return s, {}


def _old_quarterly_revenue(facts, candidates, fye_month, annual_tags):
    return N._quarterly_flow(facts, candidates, fye_month)


def build(cf, ticker, meta, rule):
    new_e, new_q = N._extract_revenue, N._quarterly_revenue
    if rule == "old":
        N._extract_revenue, N._quarterly_revenue = _old_extract_revenue, _old_quarterly_revenue
    try:
        return N.build_record(cf, ticker, meta)
    finally:
        N._extract_revenue, N._quarterly_revenue = new_e, new_q


def summary(rec):
    if not rec:
        return None
    ok, hard, _ = verify_company(rec)
    fy = rec["latest"].get("fy")
    return {
        "fy": fy,
        "revenue": rec["latest"].get("revenue"),
        "tag": rec.get("revenue_tag"),
        "verified": ok,
        "failed": [c[0] for c in hard if c[1] is False],
        "sum_check": next((f"{c[0]}: {'ok' if c[1] else 'FAIL'} ({c[2]})"
                           for c in hard if "quarters sum" in c[0]), "n/a"),
    }


def pct(a, b):
    if a in (None, 0) or b is None:
        return None
    return (b - a) / abs(a)


def main():
    idx = json.loads((DATA / "index.json").read_text())
    tmap = json.loads((DATA / "company_tickers.json").read_text())
    cik_of = {r["ticker"].upper(): CIK_OVERRIDE.get(r["ticker"].upper(), int(r["cik_str"]))
              for r in tmap.values()}
    fz = zipfile.ZipFile(FACTS_ZIP)
    names = set(fz.namelist())
    sz = zipfile.ZipFile(SUBS_ZIP) if SUBS_ZIP.exists() else None

    rows, missing = [], []
    for i, r in enumerate(idx, 1):
        tk = r["ticker"]
        p = COMP / f"{tk.replace('/', '-')}.json"
        committed = json.loads(p.read_text()) if p.exists() else None
        cik = (committed or {}).get("cik") or cik_of.get(tk)
        member = f"CIK{int(cik):010d}.json" if cik else None
        if not member or member not in names:
            missing.append(tk)
            continue
        cf = json.loads(fz.read(member))
        meta = sub_meta_from_zip(sz, f"{int(cik):010d}") if sz else {}
        try:
            old = build(cf, tk, meta, "old")
            new = build(cf, tk, meta, "new")
        except Exception as e:
            missing.append(f"{tk} ({type(e).__name__})")
            continue
        so, sn = summary(old), summary(new)
        rows.append({
            "ticker": tk, "name": r.get("name"),
            "committed_revenue": (committed or {}).get("latest", {}).get("revenue"),
            "committed_fy": (committed or {}).get("latest", {}).get("fy"),
            "old": so, "new": sn,
            "rule_change": pct(so["revenue"], sn["revenue"]) if so["fy"] == sn["fy"] else None,
        })
        if i % 500 == 0:
            print(f"  {i}/{len(idx)}", flush=True)

    by = {x["ticker"]: x for x in rows}
    changed = [x for x in rows if x["rule_change"] is not None and abs(x["rule_change"]) > THRESH]
    changed.sort(key=lambda x: abs(x["new"]["revenue"] - x["old"]["revenue"]), reverse=True)
    any_change = [x for x in rows if x["rule_change"] not in (None, 0)]
    newly_held = [x["ticker"] for x in rows if x["old"]["verified"] and not x["new"]["verified"]]
    newly_ok = [x["ticker"] for x in rows if not x["old"]["verified"] and x["new"]["verified"]]
    stale = [x for x in rows if x["committed_fy"] is not None and
             (x["old"]["fy"] != x["committed_fy"] or x["old"]["revenue"] != x["committed_revenue"])]

    def money(v):
        return "n/a" if v is None else f"${v/1e6:,.1f}M"

    L = ["# Revenue rule preview", "",
         f"Companies compared: {len(rows)} (missing from bulk: {len(missing)})",
         f"Latest-FY revenue changed by the rule at all: {len(any_change)}; by more than 5%: {len(changed)}",
         f"Newly passing verification: {len(newly_ok)} {', '.join(newly_ok[:40])}",
         f"Newly failing verification: {len(newly_held)} {', '.join(newly_held[:40])}",
         f"Committed record differs from a fresh rebuild (old rule) — stale fundamentals: {len(stale)}",
         "", "## Test set and canaries", "",
         "| ticker | FY | old rule | new rule | winning tag | sum check (old) | sum check (new) |",
         "|---|---|---|---|---|---|---|"]
    for tk in TEST_SET + CANARIES:
        x = by.get(tk)
        if not x:
            L.append(f"| {tk} | not found | | | | | |")
            continue
        L.append(f"| {tk} | {x['new']['fy']} | {money(x['old']['revenue'])} | {money(x['new']['revenue'])} | "
                 f"{x['new']['tag']} | {x['old']['sum_check']} | {x['new']['sum_check']} |")
    L += ["", "## Every company whose latest-FY revenue changes by more than 5%", "",
          "| ticker | name | FY | old | new | change | winning tag | verified (new) |",
          "|---|---|---|---|---|---|---|---|"]
    for x in changed:
        L.append(f"| {x['ticker']} | {x['name']} | {x['new']['fy']} | {money(x['old']['revenue'])} | "
                 f"{money(x['new']['revenue'])} | {x['rule_change']*100:+.1f}% | {x['new']['tag']} | "
                 f"{'yes' if x['new']['verified'] else 'HELD'} |")
    AUD.mkdir(exist_ok=True)
    (AUD / "revenue-preview.md").write_text("\n".join(L) + "\n")
    (AUD / "revenue-preview.json").write_text(json.dumps({
        "rows": rows, "missing": missing, "changed_gt5": [x["ticker"] for x in changed],
        "newly_held": newly_held, "newly_ok": newly_ok,
        "stale": [x["ticker"] for x in stale]}, indent=1))
    print("\n".join(L[:8]))


if __name__ == "__main__":
    main()
