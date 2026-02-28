"""
config.py
---------
Central configuration for the financial market report.
Defines material design colours, page layout, and all data-source mappings
(tickers, ETF proxies, FRED series IDs, sector constituents).
"""

from datetime import datetime

# ── Report metadata ────────────────────────────────────────────────────────────
REPORT_DATE  = datetime(2026, 2, 28)
REPORT_TITLE = "Global Financial Markets Report"
OUTPUT_PDF   = "financial_report_feb2026.pdf"
OUTPUT_DIR   = "/home/user/test-repo"

# ── Material Design colour palette ─────────────────────────────────────────────
C = {
    # Primary brand (Blue 800/900)
    "primary":       "#1565C0",
    "primary_light": "#1976D2",
    "primary_dark":  "#0D47A1",
    "primary_bg":    "#E3F2FD",

    # Accent (Amber)
    "accent":        "#FF8F00",
    "accent_light":  "#FFC107",

    # Semantic
    "pos":           "#2E7D32",   # Green 800
    "pos_light":     "#43A047",   # Green 600
    "pos_bg":        "#E8F5E9",   # Green 50
    "neg":           "#C62828",   # Red 800
    "neg_light":     "#E53935",   # Red 600
    "neg_bg":        "#FFEBEE",   # Red 50

    # Neutrals
    "bg":            "#FAFAFA",   # Grey 50
    "surface":       "#FFFFFF",
    "text":          "#212121",   # Grey 900
    "text2":         "#616161",   # Grey 700
    "hint":          "#9E9E9E",   # Grey 500
    "divider":       "#E0E0E0",   # Grey 300
    "grid":          "#F5F5F5",   # Grey 100

    # Sequential chart colours
    "blue":          "#1976D2",
    "red":           "#E53935",
    "green":         "#43A047",
    "orange":        "#FB8C00",
    "purple":        "#8E24AA",
    "teal":          "#00897B",
    "cyan":          "#00ACC1",
    "indigo":        "#3949AB",
    "pink":          "#D81B60",
    "deep_orange":   "#F4511E",
    "brown":         "#795548",
    "grey":          "#757575",
    "lime":          "#827717",
}

# Sequential palette list (for iterating over series)
PALETTE = [
    C["blue"], C["red"], C["green"], C["orange"], C["purple"],
    C["teal"], C["cyan"], C["indigo"], C["pink"], C["deep_orange"],
    C["brown"], C["lime"],
]

# ── Page layout ────────────────────────────────────────────────────────────────
PAGE_W   = 8.5    # inches
PAGE_H   = 11.0   # inches
PAGE_DPI = 150

# ── Market index definitions ────────────────────────────────────────────────────
# Each entry: display name → {ticker for price data, proxy ETF for flow proxy}
EQUITY_INDICES = {
    "S&P 500":    {"ticker": "^GSPC",  "etf": "SPY"},
    "Dow Jones":  {"ticker": "^DJI",   "etf": "DIA"},
    "NASDAQ 100": {"ticker": "^NDX",   "etf": "QQQ"},
    "Russell 2000": {"ticker": "^RUT", "etf": "IWM"},
    "MSCI World": {"ticker": "ACWI",   "etf": "ACWI"},
    "MSCI EM":    {"ticker": "EEM",    "etf": "EEM"},
}

BOND_INDICES = {
    "US Aggregate":    {"ticker": "AGG",  "etf": "AGG"},
    "20Y+ Treasury":   {"ticker": "TLT",  "etf": "TLT"},
    "7-10Y Treasury":  {"ticker": "IEF",  "etf": "IEF"},
    "High Yield":      {"ticker": "HYG",  "etf": "HYG"},
    "IG Corporate":    {"ticker": "LQD",  "etf": "LQD"},
    "TIPS":            {"ticker": "TIP",  "etf": "TIP"},
}

COMMODITY_INDICES = {
    "Gold":         {"ticker": "GC=F",  "etf": "GLD"},
    "WTI Crude":    {"ticker": "CL=F",  "etf": "USO"},
    "Silver":       {"ticker": "SI=F",  "etf": "SLV"},
    "Natural Gas":  {"ticker": "NG=F",  "etf": "UNG"},
    "Copper":       {"ticker": "HG=F",  "etf": "CPER"},
    "Broad Cmdty":  {"ticker": "DJP",   "etf": "DJP"},
}

# ── Sector definitions (GICS / SPDR ETFs) ─────────────────────────────────────
SECTORS = {
    "Info. Technology":   {"etf": "XLK",  "color": C["blue"]},
    "Health Care":        {"etf": "XLV",  "color": C["green"]},
    "Financials":         {"etf": "XLF",  "color": C["teal"]},
    "Cons. Discretionary":{"etf": "XLY",  "color": C["orange"]},
    "Communication Svcs": {"etf": "XLC",  "color": C["purple"]},
    "Industrials":        {"etf": "XLI",  "color": C["cyan"]},
    "Consumer Staples":   {"etf": "XLP",  "color": C["lime"]},
    "Energy":             {"etf": "XLE",  "color": C["red"]},
    "Utilities":          {"etf": "XLU",  "color": C["deep_orange"]},
    "Real Estate":        {"etf": "XLRE", "color": C["brown"]},
    "Materials":          {"etf": "XLB",  "color": C["grey"]},
}

# Top 5 tickers per sector for fundamental analysis
SECTOR_TICKERS = {
    "Info. Technology":    ["AAPL",  "MSFT",  "NVDA",  "AVGO",  "ORCL"],
    "Health Care":         ["LLY",   "UNH",   "JNJ",   "ABBV",  "MRK"],
    "Financials":          ["BRK-B", "JPM",   "V",     "MA",    "BAC"],
    "Cons. Discretionary": ["AMZN",  "TSLA",  "HD",    "BKNG",  "NKE"],
    "Communication Svcs":  ["GOOGL", "META",  "NFLX",  "DIS",   "T"],
    "Industrials":         ["GE",    "CAT",   "UNP",   "HON",   "RTX"],
    "Consumer Staples":    ["WMT",   "PG",    "COST",  "KO",    "PEP"],
    "Energy":              ["XOM",   "CVX",   "COP",   "EOG",   "SLB"],
    "Utilities":           ["NEE",   "SO",    "DUK",   "AEP",   "D"],
    "Real Estate":         ["PLD",   "AMT",   "EQIX",  "PSA",   "O"],
    "Materials":           ["LIN",   "APD",   "SHW",   "FCX",   "NEM"],
}

# ── FRED series IDs for macro data ─────────────────────────────────────────────
# Inflation
INFLATION_SERIES = {
    "CPI (Headline)": "CPIAUCSL",
    "CPI (Core)":     "CPILFESL",
    "PCE":            "PCEPI",
    "Core PCE":       "PCEPILFE",
    "PPI (Final Dem)":"PPIFID",
    "5Y Breakeven":   "T5YIE",
}

# Labor market
LABOR_SERIES = {
    "Unemployment Rate":   "UNRATE",
    "Nonfarm Payrolls":    "PAYEMS",
    "Job Openings":        "JTSJOL",
    "Initial Claims":      "ICSA",
    "LFPR":                "CIVPART",
    "Avg Hourly Earnings": "CES0500000003",
}
