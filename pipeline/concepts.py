"""
concepts.py — maps clean metric names to candidate XBRL tags.

XBRL reporting is fragmented: the same economic concept appears under
different us-gaap tags across companies and eras. For each metric we try a
priority-ordered list of candidate tags and take the first that has data.

kind:
  "flow"   -> duration fact (income statement, cash flow). Annual value is the
              ~365-day period; we keep fp==FY entries from 10-K filings.
  "instant"-> point-in-time fact (balance sheet). Keep fiscal-year-end values.
  "pershare"-> USD/shares duration fact.
"""

# unit, kind, [candidate tags in priority order]
FLOW = "flow"
INSTANT = "instant"
PERSHARE = "pershare"

CONCEPTS = {
    # ---- income statement (USD, flow) ----
    "revenue": (FLOW, "USD", [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueGoodsNet",
    ]),
    "cost_of_revenue": (FLOW, "USD", [
        "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold",
    ]),
    "gross_profit": (FLOW, "USD", ["GrossProfit"]),
    "operating_income": (FLOW, "USD", ["OperatingIncomeLoss"]),
    "net_income": (FLOW, "USD", ["NetIncomeLoss", "ProfitLoss"]),
    "rd_expense": (FLOW, "USD", ["ResearchAndDevelopmentExpense"]),
    "interest_expense": (FLOW, "USD", ["InterestExpense", "InterestExpenseDebt"]),
    "income_tax": (FLOW, "USD", ["IncomeTaxExpenseBenefit"]),
    "pretax_income": (FLOW, "USD", [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ]),

    # ---- cash flow (USD, flow) ----
    "op_cash_flow": (FLOW, "USD", [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ]),
    "capex": (FLOW, "USD", [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForCapitalImprovements",
    ]),
    "dividends_paid": (FLOW, "USD", [
        "PaymentsOfDividendsCommonStock", "PaymentsOfDividends",
    ]),
    "dividends_per_share": (PERSHARE, "USD/shares", [
        "CommonStockDividendsPerShareDeclared",
        "CommonStockDividendsPerShareCashPaid",
    ]),

    # ---- balance sheet (USD, instant) ----
    "assets": (INSTANT, "USD", ["Assets"]),
    "current_assets": (INSTANT, "USD", ["AssetsCurrent"]),
    "liabilities": (INSTANT, "USD", ["Liabilities"]),
    "current_liabilities": (INSTANT, "USD", ["LiabilitiesCurrent"]),
    "equity": (INSTANT, "USD", [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ]),
    "cash": (INSTANT, "USD", [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ]),
    "long_term_debt": (INSTANT, "USD", [
        "LongTermDebtNoncurrent", "LongTermDebt",
    ]),
    "short_term_debt": (INSTANT, "USD", [
        "DebtCurrent", "ShortTermBorrowings", "LongTermDebtCurrent",
    ]),
    "inventory": (INSTANT, "USD", ["InventoryNet"]),

    # ---- per share (USD/shares, flow) ----
    "eps_diluted": (PERSHARE, "USD/shares", [
        "EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted",
    ]),
    "eps_basic": (PERSHARE, "USD/shares", ["EarningsPerShareBasic"]),
}

# shares outstanding handled separately (dei taxonomy, instant, "shares" unit)
SHARES_TAGS = [
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
]
WEIGHTED_DILUTED_TAG = ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding")
