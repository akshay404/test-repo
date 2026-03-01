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

# Top 10 tickers per sector for constituent performance analysis
SECTOR_TICKERS = {
    "Info. Technology":    ["AAPL",  "MSFT",  "NVDA",  "AVGO",  "ORCL",  "AMD",  "INTC", "QCOM", "CRM",  "ADBE"],
    "Health Care":         ["LLY",   "UNH",   "JNJ",   "ABBV",  "MRK",   "CVS",  "MDT",  "ISRG", "TMO",  "BMY"],
    "Financials":          ["BRK-B", "JPM",   "V",     "MA",    "BAC",   "GS",   "MS",   "C",    "WFC",  "AXP"],
    "Cons. Discretionary": ["AMZN",  "TSLA",  "HD",    "BKNG",  "NKE",   "LOW",  "TGT",  "GM",   "F",    "SBUX"],
    "Communication Svcs":  ["GOOGL", "META",  "NFLX",  "DIS",   "T",     "CHTR", "EA",   "TTWO", "IPG",  "OMC"],
    "Industrials":         ["GE",    "CAT",   "UNP",   "HON",   "RTX",   "MMM",  "DE",   "LMT",  "BA",   "FDX"],
    "Consumer Staples":    ["WMT",   "PG",    "COST",  "KO",    "PEP",   "CL",   "MDLZ", "STZ",  "PM",   "MO"],
    "Energy":              ["XOM",   "CVX",   "COP",   "EOG",   "SLB",   "OXY",  "PSX",  "VLO",  "HAL",  "DVN"],
    "Utilities":           ["NEE",   "SO",    "DUK",   "AEP",   "D",     "EXC",  "PCG",  "AWK",  "ETR",  "WEC"],
    "Real Estate":         ["PLD",   "AMT",   "EQIX",  "PSA",   "O",     "SPG",  "ARE",  "VTR",  "EQR",  "AVB"],
    "Materials":           ["LIN",   "APD",   "SHW",   "FCX",   "NEM",   "PPG",  "NUE",  "VMC",  "MOS",  "ALB"],
}

# ── Street analyst consensus views (Feb 2026, simulated) ──────────────────────
ANALYST_VIEWS = {
    "Info. Technology":    {"rating": "OW", "buys": 28, "holds": 8,  "sells": 2},
    "Health Care":         {"rating": "N",  "buys": 18, "holds": 15, "sells": 5},
    "Financials":          {"rating": "OW", "buys": 22, "holds": 12, "sells": 3},
    "Cons. Discretionary": {"rating": "N",  "buys": 16, "holds": 18, "sells": 6},
    "Communication Svcs":  {"rating": "OW", "buys": 20, "holds": 10, "sells": 3},
    "Industrials":         {"rating": "OW", "buys": 19, "holds": 13, "sells": 4},
    "Consumer Staples":    {"rating": "UW", "buys": 10, "holds": 18, "sells": 10},
    "Energy":              {"rating": "N",  "buys": 15, "holds": 16, "sells": 8},
    "Utilities":           {"rating": "N",  "buys": 12, "holds": 17, "sells": 8},
    "Real Estate":         {"rating": "N",  "buys": 14, "holds": 16, "sells": 7},
    "Materials":           {"rating": "N",  "buys": 13, "holds": 17, "sells": 6},
}

# ── Key event annotations for 10Y sector ETF charts ───────────────────────────
# Each entry: list of (datetime, brief_label) tuples
SECTOR_EVENTS = {
    "Info. Technology": [
        (datetime(2018, 10,  3), "Rate shock"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2021, 11, 19), "Tech peak"),
        (datetime(2022, 10, 13), "Bear low"),
        (datetime(2023,  7, 19), "AI rally"),
    ],
    "Health Care": [
        (datetime(2018, 12, 24), "Rate shock"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2021,  8,  9), "Delta wave"),
        (datetime(2022,  6, 16), "Rate fears"),
        (datetime(2024,  7, 11), "Drug pricing"),
    ],
    "Financials": [
        (datetime(2018, 12, 24), "Fed pause"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2022,  1,  3), "Rate lift-off"),
        (datetime(2023,  3, 10), "SVB crisis"),
        (datetime(2024, 11,  6), "Trump rally"),
    ],
    "Cons. Discretionary": [
        (datetime(2018, 12, 24), "Trade war"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2021, 11, 16), "Peak"),
        (datetime(2022, 10, 13), "Bear low"),
        (datetime(2023,  2,  2), "Soft landing"),
    ],
    "Communication Svcs": [
        (datetime(2018, 12, 24), "FAANG selloff"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2021,  9,  7), "ATH"),
        (datetime(2022, 10, 13), "Bear low"),
        (datetime(2023,  7, 26), "AI/ad rally"),
    ],
    "Industrials": [
        (datetime(2018, 12, 24), "Trade war"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2022,  9, 26), "Rate peak"),
        (datetime(2023,  1, 23), "China reopens"),
        (datetime(2025,  1, 20), "Tariff fears"),
    ],
    "Consumer Staples": [
        (datetime(2018, 12, 24), "Defensive bid"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2022,  9, 26), "Defensive peak"),
        (datetime(2023,  7, 13), "Relative low"),
        (datetime(2024,  9, 18), "Fed cut"),
    ],
    "Energy": [
        (datetime(2018, 12, 24), "Oil selloff"),
        (datetime(2020,  4, 21), "Oil <$0"),
        (datetime(2021, 10, 26), "Recovery"),
        (datetime(2022,  6,  8), "War peak"),
        (datetime(2023,  9, 28), "OPEC+ cut"),
    ],
    "Utilities": [
        (datetime(2018, 12, 24), "Defensive bid"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2022,  4, 21), "Rate fears"),
        (datetime(2023, 10,  6), "Rate peak"),
        (datetime(2024,  9, 18), "Fed cut rally"),
    ],
    "Real Estate": [
        (datetime(2018, 12, 24), "Rate fears"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2022,  1,  3), "Rate lift-off"),
        (datetime(2023, 10,  6), "Rate peak"),
        (datetime(2024,  9, 18), "Fed cut rally"),
    ],
    "Materials": [
        (datetime(2018, 12, 24), "Trade war"),
        (datetime(2020,  3, 23), "COVID low"),
        (datetime(2021,  5, 10), "Cmdty peak"),
        (datetime(2022,  9, 26), "Bear low"),
        (datetime(2024, 10,  1), "China stim."),
    ],
}

# ── Macro stress event shading for 10Y charts ─────────────────────────────────
# Each entry: (start_date, end_date, brief_label)
MACRO_STRESS_EVENTS = [
    (datetime(2018, 10,  3), datetime(2018, 12, 24), "Fed tightening"),
    (datetime(2020,  2, 19), datetime(2020,  4, 30), "COVID"),
    (datetime(2022,  1,  3), datetime(2022, 10, 13), "Rate hike cycle"),
    (datetime(2023,  3,  8), datetime(2023,  5,  1), "SVB crisis"),
]

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
