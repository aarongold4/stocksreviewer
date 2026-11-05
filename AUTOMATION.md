# Autonomous operation — stocksreviewer.com

The site updates, audits, corrects, and deploys **itself every day** with nothing
of yours switched on. The engine is **GitHub Actions** (runs on GitHub's servers,
free), not your Mac and not a chat session.

## The two loops

**1. Data + deploy loop — GitHub Actions (`.github/workflows/update.yml`)**
- **Nightly (Mon–Sat, 05:10 ET):** re-fetch all prices → self-audit → rebuild → deploy.
- **Weekly (Sun):** also re-pull SEC bulk filings so new 10-Q/10-K numbers land.
- Every run ends with `pipeline/audit.py`, which **blocks the deploy** if the data
  looks broken (count cliff, missing mega-cap, stale/blocked prices, corruption).
  A blocked run fails the job → GitHub emails you → the live site stays as-is.
  Nothing wrong ever goes live unattended.

**2. Editorial loop — optional Claude scheduled task (weekly)**
Reads the week's audit report, flags anything needing a human call (a vanished
mega-cap, an odd mover), and drafts new content for you to one-click publish —
the same pattern as creditcardreview.org / onlinebankreview.com.

## "Nothing publishes that can't be verified" (pipeline/verify.py + the gate)

The real failure mode of an unattended pipeline isn't a wrong SEC number (the
filing is the authority) — it's OUR extraction misreading it (wrong tag, a
year-to-date value mistaken for a discrete quarter, a unit error). Every such
bug leaves a fingerprint: the statements stop cross-footing. So each company is
reconciled against itself on true invariants — **quarterly revenues must sum to
the annual**, and **TTM must equal the sum of the last four quarters**. A company
that fails is HELD: `build.py` excludes it from the published site entirely. It
is never shown with an unverified number.

- Worked example: Micron's real FY2026 +256% jump to $133.2B **passes** (its
  discrete quarters genuinely sum to the annual) and publishes. A cumulative-
  extraction bug would make the "quarters" sum to ~3× the annual → held.
- Soft checks (assets = liabilities + equity; gross profit = revenue − COGS)
  legitimately fail on non-controlling interests and financial companies, so they
  are reported (`data/audit/soft-flags.json`), never gating.
- Held companies are listed in `data/audit/unverified.json`. The **daily
  verification task** (a scheduled Claude task, already created) checks each held
  company against its actual SEC filing; a filing-confirmed one is added to
  `data/verified_overrides.json`, which lets `build.py` publish it on the next
  build. Nothing is force-published to make the count look complete.

Today's gate holds 7 merger/transition-period companies (e.g. Magnera, Republic
Airways) whose quarterly extraction is genuinely unreliable; 5,628 verified
companies publish.

## What "audits and corrects itself" means (pipeline/audit.py)

Self-corrects automatically:
- **Predecessor-CIK fallback** (`CIK_OVERRIDE` in `build_from_bulk.py`) — when a
  company reincorporates under a new CIK with no annual filing yet (ExxonMobil did
  this in 2026), it pulls history from the prior entity instead of dropping it.
- **Non-operating exclusion** — commodity ETFs/trusts that report negative revenue
  are dropped (they aren't companies).
- **Stale-price safety** — keeps yesterday's prices for any ticker that fails to
  fetch, rather than publishing blanks.

Refuses to deploy (blocks, emails you) on:
- company count below 5,000 or down >5% vs last deploy;
- any canary mega-cap (40 names) missing or zero-revenue;
- price coverage <85% or newest price >5 days old (source blocked/rate-limited);
- >10 companies with negative revenue or impossible future fiscal years.

Each run writes `data/audit/report-<date>.md` and `data/audit/status.json`.

## One-time setup (≈15 min, only you can do these)

1. **Create the repo** (matches your creditcardreview pattern):
   ```
   gh repo create aarongold4/stocksreviewer --private --source=. --push
   ```
   (or make it on github.com and `git push`). The provided `.gitignore` keeps the
   2.9 GB SEC archives and the 226 MB `dist/` out of git.

2. **Add deploy secrets** — repo Settings → Secrets and variables → Actions → New:
   - `HOSTINGER_FTP_HOST` — e.g. `ftp.stocksreviewer.com` or the server IP
   - `HOSTINGER_FTP_USER` — your Hostinger FTP username
   - `HOSTINGER_FTP_PASS` — your Hostinger FTP password
   (Hostinger → Files → FTP Accounts shows these.)

3. **First manual run:** Actions tab → "StocksReviewer auto-update" → Run workflow
   → mode `full`. Watch it go green. After that it's on the schedule.

That's it. No step 4 — it runs itself.

## Deploy method

Default is **FTPS mirror** (`scripts/deploy_dist.sh`) — only changed files move.
If you'd rather use **Hostinger Git auto-deploy** (like creditcardreview), the
script has a commented orphan-`deploy`-branch block; swap it in and point
Hostinger at the `deploy` branch instead of adding FTP secrets.

## The one risk to watch

Prices come from Yahoo's free endpoint. From GitHub's datacenter IPs it may
rate-limit. The audit catches this (coverage/staleness block → you get emailed),
so it fails loudly, never silently. If it becomes chronic, swap `pipeline/prices.py`
for a licensed feed (a cheap paid API, or Bright Data) — it's one isolated file.

## Costs

GitHub Actions: ~15–40 min/run. Nightly prices + weekly full ≈ well within the
free tier for a private repo; public repo is unlimited. SEC and Yahoo are free.
