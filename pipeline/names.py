"""
names.py — turn EDGAR entity names into clean display names.

EDGAR casing is inconsistent: some names arrive properly cased ("Apple Inc."),
others all-caps ("WALMART INC."). Title-casing everything would break the good
ones ("NVIDIA" -> "Nvidia", "UnitedHealth" -> "Unitedhealth"). So:

  * already-mixed-case names: keep their casing, just strip the legal suffix.
  * all-caps names: smart title-case, keep known acronyms upper.
  * marquee tickers: exact branding via TICKER_NAMES.
"""
import re

SUFFIXES = {
    "inc", "inc.", "incorporated", "corp", "corp.", "corporation", "co",
    "co.", "company", "companies", "ltd", "ltd.", "limited", "plc", "llc",
    "l.l.c.", "llp", "lp", "l.p.", "holdings", "holding", "hldgs", "sa",
    "s.a.", "nv", "n.v.", "ag", "se", "the",
}
SMALL = {"of", "and", "the", "for", "to", "in", "on", "at", "by", "de",
         "von", "van", "da", "del", "le"}
# words to keep fully uppercase when source was all-caps
KEEP_UPPER = {
    "NVIDIA", "IBM", "AMD", "HP", "HPE", "AT&T", "UPS", "USA", "US", "PNC",
    "KLA", "NXP", "DXC", "CDW", "SAP", "ON", "PG&E", "GE", "GM", "TJX",
    "PPG", "MSCI", "CME", "ICE", "S&P", "3M", "BNY", "AECOM", "EPAM",
    "FMC", "IQVIA", "DTE", "WEC", "CMS", "NRG", "PSEG", "AES",
}
# tricky internal-caps words
CAMEL = {
    "jpmorgan": "JPMorgan", "mcdonald's": "McDonald's", "mcdonalds": "McDonald's",
    "mckesson": "McKesson", "mccormick": "McCormick", "ebay": "eBay",
    "paypal": "PayPal", "lyondellbasell": "LyondellBasell", "biomarin": "BioMarin",
    "verisign": "VeriSign", "ansys": "ANSYS", "fedex": "FedEx",
    "powerschool": "PowerSchool", "servicenow": "ServiceNow",
}
# exact display names for the best-known tickers
TICKER_NAMES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon",
    "GOOGL": "Alphabet (Google)", "GOOG": "Alphabet (Google)", "META": "Meta",
    "TSLA": "Tesla", "BRK-B": "Berkshire Hathaway", "BRK-A": "Berkshire Hathaway",
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "WMT": "Walmart",
    "V": "Visa", "MA": "Mastercard", "UNH": "UnitedHealth Group",
    "XOM": "ExxonMobil", "CVX": "Chevron", "KO": "Coca-Cola", "PEP": "PepsiCo",
    "JNJ": "Johnson & Johnson", "PG": "Procter & Gamble", "HD": "Home Depot",
    "COST": "Costco", "DIS": "Disney", "NFLX": "Netflix", "CRM": "Salesforce",
    "ORCL": "Oracle", "ADBE": "Adobe", "INTC": "Intel", "QCOM": "Qualcomm",
    "T": "AT&T", "VZ": "Verizon", "CMCSA": "Comcast", "PFE": "Pfizer",
    "MRK": "Merck", "ABBV": "AbbVie", "TMO": "Thermo Fisher Scientific",
    "MCD": "McDonald's", "NKE": "Nike", "BA": "Boeing", "CAT": "Caterpillar",
    "GE": "GE Aerospace", "IBM": "IBM", "GS": "Goldman Sachs", "MS": "Morgan Stanley",
    "AMD": "AMD", "AVGO": "Broadcom", "TXN": "Texas Instruments",
    "PYPL": "PayPal", "SBUX": "Starbucks", "LMT": "Lockheed Martin",
    "BLK": "BlackRock", "C": "Citigroup", "WFC": "Wells Fargo",
}

_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
_SLASH = re.compile(r"\s*/[A-Za-z]{1,3}/?\s*$")


def _smart_token(tok, first):
    bare = tok.strip(".,")
    up = bare.upper()
    if up in KEEP_UPPER:
        return up
    low = bare.lower()
    if low in CAMEL:
        return CAMEL[low]
    # acronym heuristic: short, all letters, no vowels -> keep upper
    if 2 <= len(bare) <= 4 and bare.isalpha() and not (set(bare.upper()) & set("AEIOUY")):
        return up
    if low in SMALL and not first:
        return low
    # hyphen / apostrophe: capitalize each part
    if "-" in bare:
        return "-".join(p.capitalize() for p in bare.split("-"))
    if "'" in bare and not bare.lower().endswith("'s"):
        return "'".join(p.capitalize() for p in bare.split("'"))
    if bare.lower().endswith("'s"):
        return bare[:-2].capitalize() + "'s"
    return bare.capitalize()


def clean_name(raw):
    if not raw:
        return raw
    s = _PAREN.sub("", raw.strip())
    s = _SLASH.sub("", s)
    s = s.rstrip(".").strip()
    toks = s.split()
    # strip leading "The"
    if toks and toks[0].lower() == "the":
        toks = toks[1:]
    # strip trailing legal suffixes / class markers / stray "&"
    while toks:
        last = toks[-1].lower().strip(".,")
        last_nodot = last.replace(".", "")
        if last in SUFFIXES or last_nodot in SUFFIXES or last_nodot in {"nv", "sa", "ag", "se", "plc", "llc", "lp"} or last in {"&", "cl", "class", "a", "b", "com", "new"}:
            toks.pop()
        else:
            break
    if not toks:
        toks = s.split()
    name = " ".join(toks).strip().rstrip(",").strip()

    has_lower = any(c.islower() for c in name)
    if has_lower:
        # already cased by the source; leave as-is
        return name
    # all-caps -> smart title-case
    parts = name.split()
    return " ".join(_smart_token(t, i == 0) for i, t in enumerate(parts))


def display_name(ticker, raw):
    if ticker and ticker.upper() in TICKER_NAMES:
        return TICKER_NAMES[ticker.upper()]
    return clean_name(raw)
