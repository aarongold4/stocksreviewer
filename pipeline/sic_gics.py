"""
sic_gics.py — map SEC SIC codes to a Fidelity-style GICS taxonomy.

EDGAR classifies filers by SIC (a government scheme). Fidelity (and most of the
investing world) uses GICS: 11 sectors, each split into industries. There is no
free official SIC->GICS crosswalk, so this is a curated mapping:

  * SPECIFIC: exact 4-digit SIC -> (sector, industry) for the codes that carry
    the big, well-known names (semiconductors, software, pharma, banks, etc.).
  * RANGES: lo-hi SIC bands -> (sector, industry) as a fallback for the long tail.

classify(sic) returns (sector, industry); unknown/blank -> ("Unclassified", "Other").
The 11 sectors match Fidelity's sector list exactly.
"""

SECTORS = [
    "Communication Services", "Consumer Discretionary", "Consumer Staples",
    "Energy", "Financials", "Health Care", "Industrials",
    "Information Technology", "Materials", "Real Estate", "Utilities",
]

# exact SIC -> (sector, industry)
SPECIFIC = {
    "100": ("Consumer Staples", "Agricultural Products"),
    "1311": ("Energy", "Oil & Gas Exploration & Production"),
    "1381": ("Energy", "Oil & Gas Equipment & Services"),
    "1389": ("Energy", "Oil & Gas Equipment & Services"),
    "1040": ("Materials", "Gold & Precious Metals"),
    "1000": ("Materials", "Metals & Mining"),
    "2911": ("Energy", "Oil & Gas Refining & Marketing"),
    "2080": ("Consumer Staples", "Beverages"),
    "2086": ("Consumer Staples", "Beverages"),
    "2090": ("Consumer Staples", "Packaged Foods"),
    "2000": ("Consumer Staples", "Packaged Foods"),
    "2111": ("Consumer Staples", "Tobacco"),
    "2300": ("Consumer Discretionary", "Apparel & Luxury Goods"),
    "2731": ("Communication Services", "Publishing"),
    "2834": ("Health Care", "Pharmaceuticals"),
    "2836": ("Health Care", "Biotechnology"),
    "2835": ("Health Care", "Life Sciences Tools & Services"),
    "3570": ("Information Technology", "Technology Hardware & Equipment"),
    "3571": ("Information Technology", "Technology Hardware & Equipment"),
    "3572": ("Information Technology", "Technology Hardware & Equipment"),
    "3576": ("Information Technology", "Communications Equipment"),
    "3577": ("Information Technology", "Technology Hardware & Equipment"),
    "3661": ("Information Technology", "Communications Equipment"),
    "3663": ("Information Technology", "Communications Equipment"),
    "3669": ("Information Technology", "Communications Equipment"),
    "3674": ("Information Technology", "Semiconductors"),
    "3559": ("Information Technology", "Semiconductor Equipment"),
    "3711": ("Consumer Discretionary", "Automobiles"),
    "3713": ("Consumer Discretionary", "Automobiles"),
    "3714": ("Consumer Discretionary", "Auto Components"),
    "3721": ("Industrials", "Aerospace & Defense"),
    "3724": ("Industrials", "Aerospace & Defense"),
    "3728": ("Industrials", "Aerospace & Defense"),
    "3760": ("Industrials", "Aerospace & Defense"),
    "3812": ("Industrials", "Aerospace & Defense"),
    "3841": ("Health Care", "Health Care Equipment"),
    "3845": ("Health Care", "Health Care Equipment"),
    "3826": ("Health Care", "Life Sciences Tools & Services"),
    "4011": ("Industrials", "Road & Rail"),
    "4512": ("Industrials", "Airlines"),
    "4513": ("Industrials", "Air Freight & Logistics"),
    "4813": ("Communication Services", "Telecom Services"),
    "4812": ("Communication Services", "Wireless Telecom"),
    "4833": ("Communication Services", "Broadcasting"),
    "4841": ("Communication Services", "Media & Entertainment"),
    "4899": ("Communication Services", "Telecom Services"),
    "4900": ("Utilities", "Multi-Utilities"),
    "4911": ("Utilities", "Electric Utilities"),
    "4922": ("Utilities", "Gas Utilities"),
    "4924": ("Utilities", "Gas Utilities"),
    "4931": ("Utilities", "Multi-Utilities"),
    "5411": ("Consumer Staples", "Food Retail"),
    "5912": ("Consumer Staples", "Drug Retail"),
    "5331": ("Consumer Discretionary", "General Merchandise Stores"),
    "5651": ("Consumer Discretionary", "Apparel Retail"),
    "5961": ("Consumer Discretionary", "Internet & Direct Marketing Retail"),
    "5734": ("Consumer Discretionary", "Specialty Retail"),
    "5945": ("Consumer Discretionary", "Specialty Retail"),
    "5990": ("Consumer Discretionary", "Specialty Retail"),
    "6021": ("Financials", "Banks"),
    "6022": ("Financials", "Banks"),
    "6029": ("Financials", "Banks"),
    "6199": ("Financials", "Consumer Finance"),
    "6200": ("Financials", "Capital Markets"),
    "6211": ("Financials", "Capital Markets"),
    "6311": ("Financials", "Insurance"),
    "6321": ("Financials", "Insurance"),
    "6331": ("Financials", "Insurance"),
    "6411": ("Financials", "Insurance"),
    "6500": ("Real Estate", "Real Estate Management & Development"),
    "6798": ("Real Estate", "REITs"),
    "6770": ("Financials", "Shell Companies"),
    "7011": ("Consumer Discretionary", "Hotels, Restaurants & Leisure"),
    "7372": ("Information Technology", "Software"),
    "7370": ("Information Technology", "IT Services"),
    "7371": ("Information Technology", "IT Services"),
    "7374": ("Information Technology", "IT Services"),
    "7389": ("Industrials", "Commercial Services"),
    "7812": ("Communication Services", "Media & Entertainment"),
    "7990": ("Consumer Discretionary", "Leisure"),
    "7997": ("Consumer Discretionary", "Leisure"),
    "8000": ("Health Care", "Health Care Providers & Services"),
    "8011": ("Health Care", "Health Care Providers & Services"),
    "8060": ("Health Care", "Health Care Facilities"),
    "8062": ("Health Care", "Health Care Facilities"),
    "8090": ("Health Care", "Health Care Providers & Services"),
    "8731": ("Health Care", "Life Sciences Tools & Services"),
}

# (lo, hi, sector, industry) inclusive ranges — fallback
RANGES = [
    (100, 999, "Consumer Staples", "Agricultural Products"),
    (1000, 1099, "Materials", "Metals & Mining"),
    (1200, 1299, "Energy", "Coal & Consumable Fuels"),
    (1300, 1399, "Energy", "Oil, Gas & Consumable Fuels"),
    (1400, 1499, "Materials", "Construction Materials"),
    (1500, 1599, "Consumer Discretionary", "Homebuilding"),
    (1600, 1799, "Industrials", "Construction & Engineering"),
    (2000, 2199, "Consumer Staples", "Packaged Foods"),
    (2200, 2399, "Consumer Discretionary", "Apparel & Luxury Goods"),
    (2400, 2499, "Materials", "Paper & Forest Products"),
    (2500, 2599, "Consumer Discretionary", "Household Durables"),
    (2600, 2699, "Materials", "Paper & Forest Products"),
    (2700, 2799, "Communication Services", "Publishing"),
    (2800, 2829, "Materials", "Chemicals"),
    (2830, 2836, "Health Care", "Pharmaceuticals"),
    (2840, 2899, "Materials", "Chemicals"),
    (2900, 2999, "Energy", "Oil & Gas Refining & Marketing"),
    (3000, 3099, "Materials", "Chemicals"),
    (3100, 3199, "Consumer Discretionary", "Textiles, Apparel & Luxury"),
    (3200, 3299, "Materials", "Construction Materials"),
    (3300, 3399, "Materials", "Metals & Mining"),
    (3400, 3499, "Industrials", "Building Products"),
    (3500, 3569, "Industrials", "Machinery"),
    (3570, 3579, "Information Technology", "Technology Hardware & Equipment"),
    (3580, 3599, "Industrials", "Machinery"),
    (3600, 3629, "Industrials", "Electrical Equipment"),
    (3630, 3669, "Information Technology", "Communications Equipment"),
    (3670, 3679, "Information Technology", "Semiconductors"),
    (3680, 3699, "Information Technology", "Technology Hardware & Equipment"),
    (3700, 3716, "Consumer Discretionary", "Automobiles & Components"),
    (3720, 3769, "Industrials", "Aerospace & Defense"),
    (3770, 3799, "Industrials", "Machinery"),
    (3800, 3829, "Information Technology", "Electronic Instruments"),
    (3830, 3859, "Health Care", "Health Care Equipment"),
    (3860, 3899, "Consumer Discretionary", "Household Durables"),
    (3900, 3999, "Consumer Discretionary", "Leisure Products"),
    (4000, 4499, "Industrials", "Transportation"),
    (4500, 4599, "Industrials", "Airlines"),
    (4600, 4789, "Industrials", "Transportation"),
    (4800, 4829, "Communication Services", "Telecom Services"),
    (4830, 4899, "Communication Services", "Media & Entertainment"),
    (4900, 4991, "Utilities", "Utilities"),
    (5000, 5199, "Industrials", "Trading Companies & Distributors"),
    (5200, 5399, "Consumer Discretionary", "Multiline Retail"),
    (5400, 5499, "Consumer Staples", "Food & Staples Retailing"),
    (5500, 5799, "Consumer Discretionary", "Specialty Retail"),
    (5800, 5899, "Consumer Discretionary", "Hotels, Restaurants & Leisure"),
    (5900, 5999, "Consumer Discretionary", "Specialty Retail"),
    (6000, 6199, "Financials", "Banks"),
    (6200, 6299, "Financials", "Capital Markets"),
    (6300, 6499, "Financials", "Insurance"),
    (6500, 6599, "Real Estate", "Real Estate Management & Development"),
    (6600, 6799, "Financials", "Diversified Financials"),
    (7000, 7099, "Consumer Discretionary", "Hotels, Restaurants & Leisure"),
    (7100, 7299, "Industrials", "Commercial Services"),
    (7300, 7369, "Industrials", "Commercial Services"),
    (7370, 7379, "Information Technology", "IT Services"),
    (7380, 7399, "Industrials", "Commercial Services"),
    (7400, 7799, "Industrials", "Commercial Services"),
    (7800, 7899, "Communication Services", "Media & Entertainment"),
    (7900, 7999, "Consumer Discretionary", "Hotels, Restaurants & Leisure"),
    (8000, 8099, "Health Care", "Health Care Providers & Services"),
    (8100, 8699, "Industrials", "Professional Services"),
    (8700, 8799, "Health Care", "Life Sciences Tools & Services"),
    (8800, 8999, "Industrials", "Professional Services"),
]


# Ticker-level overrides for prominent names where SIC and GICS genuinely
# disagree (GICS classifies at the company level; SIC does not). Keeps the
# best-known tickers correct; the long tail falls back to the SIC mapping.
TICKER_OVERRIDES = {
    "WMT": ("Consumer Staples", "Food & Staples Retailing"),
    "COST": ("Consumer Staples", "Food & Staples Retailing"),
    "TGT": ("Consumer Discretionary", "General Merchandise Stores"),
    "AMZN": ("Consumer Discretionary", "Internet & Direct Marketing Retail"),
    "TSLA": ("Consumer Discretionary", "Automobiles"),
    "GOOGL": ("Communication Services", "Interactive Media & Services"),
    "GOOG": ("Communication Services", "Interactive Media & Services"),
    "META": ("Communication Services", "Interactive Media & Services"),
    "NFLX": ("Communication Services", "Entertainment"),
    "DIS": ("Communication Services", "Entertainment"),
    "CMCSA": ("Communication Services", "Media"),
    "V": ("Financials", "Transaction & Payment Processing"),
    "MA": ("Financials", "Transaction & Payment Processing"),
    "PYPL": ("Financials", "Transaction & Payment Processing"),
    "BRK-B": ("Financials", "Diversified Financials"),
    "BRK-A": ("Financials", "Diversified Financials"),
    "AAPL": ("Information Technology", "Technology Hardware & Equipment"),
    "ABNB": ("Consumer Discretionary", "Hotels, Restaurants & Leisure"),
    "UBER": ("Industrials", "Ground Transportation"),
    "PG": ("Consumer Staples", "Household & Personal Products"),
    "KO": ("Consumer Staples", "Beverages"),
    "PEP": ("Consumer Staples", "Beverages"),
    "HD": ("Consumer Discretionary", "Specialty Retail"),
    "LOW": ("Consumer Discretionary", "Specialty Retail"),
    "MCD": ("Consumer Discretionary", "Hotels, Restaurants & Leisure"),
    "NKE": ("Consumer Discretionary", "Textiles, Apparel & Luxury"),
}


def classify(sic, ticker=None):
    if ticker and ticker.upper() in TICKER_OVERRIDES:
        return TICKER_OVERRIDES[ticker.upper()]
    if not sic:
        return ("Unclassified", "Other")
    s = str(sic).strip().lstrip("0") or "0"
    if s in SPECIFIC:
        return SPECIFIC[s]
    # also try zero-padded original key form used in SPECIFIC (e.g. "100")
    if str(sic).strip() in SPECIFIC:
        return SPECIFIC[str(sic).strip()]
    try:
        n = int(s)
    except ValueError:
        return ("Unclassified", "Other")
    for lo, hi, sector, industry in RANGES:
        if lo <= n <= hi:
            return (sector, industry)
    return ("Unclassified", "Other")
