"""
data_simulator.py
-----------------
Generates statistically realistic synthetic market data when live
internet access is unavailable.

All numbers are plausible as of February 2026, calibrated to:
  • S&P 500 ~5,850 (moderate 2025 gains, slight early-2026 pullback)
  • 10Y yield ~4.3%
  • VIX ~16 (calm market)
  • CPI ~2.8% YoY (gradual disinflation)
  • Unemployment ~4.1%

Pages produced with this data will be watermarked "SIMULATED DATA".
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from financial_report.config import (
    EQUITY_INDICES, BOND_INDICES, COMMODITY_INDICES,
    SECTORS, SECTOR_TICKERS, C,
)

rng = np.random.default_rng(42)   # reproducible


# ── helpers ────────────────────────────────────────────────────────────────────

def _gbm(start_price: float, n_days: int, mu: float, sigma: float,
         seed: int = 0) -> pd.Series:
    """Geometric Brownian Motion price series."""
    local_rng = np.random.default_rng(seed)
    dt = 1 / 252
    returns = local_rng.normal((mu - 0.5 * sigma**2) * dt,
                                sigma * np.sqrt(dt), n_days)
    prices = start_price * np.cumprod(np.exp(returns))
    end   = datetime(2026, 2, 27)   # last business day (Feb 28 is Saturday)
    dates = pd.bdate_range(end=end, periods=n_days + 5)[-n_days:]  # always exact n_days
    return pd.Series(prices, index=dates)


def _macro_series(start_val: float, n_months: int, mu: float,
                  sigma: float, trend: float = 0.0, seed: int = 0) -> pd.Series:
    """Monthly macro series (level)."""
    local_rng = np.random.default_rng(seed)
    vals = [start_val]
    for i in range(1, n_months):
        noise  = local_rng.normal(0, sigma)
        vals.append(vals[-1] + mu + trend * i + noise)
    end   = datetime(2026, 2, 1)
    dates = pd.date_range(end=end, periods=n_months, freq="MS")
    return pd.Series(vals, index=dates)


# ── Section 1: Market Overview ─────────────────────────────────────────────────

# (mu, sigma, start_price, flow_3m_B)
_INDEX_PARAMS = {
    # Equity
    "S&P 500":      (0.12, 0.14, 4_500, +18.4),
    "Dow Jones":    (0.10, 0.12, 37_000, +12.1),
    "NASDAQ 100":   (0.18, 0.20, 15_800, +24.7),
    "Russell 2000": (0.08, 0.18, 1_900, -3.2),
    "MSCI World":   (0.11, 0.13, 98,    +9.5),
    "MSCI EM":      (0.07, 0.17, 42,    -5.8),
    # Fixed Income
    "US Aggregate": (0.04, 0.05, 98,    +6.1),
    "20Y+ Treasury":(0.02, 0.10, 92,    -4.3),
    "7-10Y Treasury":(0.04, 0.06, 96,   +2.8),
    "High Yield":   (0.07, 0.07, 78,    +8.9),
    "IG Corporate": (0.05, 0.05, 110,   +3.7),
    "TIPS":         (0.03, 0.05, 108,   +1.2),
    # Commodities
    "Gold":         (0.10, 0.12, 1_900, +11.3),
    "WTI Crude":    (0.05, 0.30, 72,    -8.7),
    "Silver":       (0.12, 0.22, 22,    +4.2),
    "Natural Gas":  (-0.05,0.45, 2.8,   -12.1),
    "Copper":       (0.08, 0.20, 3.8,   +3.6),
    "Broad Cmdty":  (0.04, 0.15, 28,    -2.4),
}

_CAT_MAP = {
    **{k: "Equity"       for k in EQUITY_INDICES},
    **{k: "Fixed Income" for k in BOND_INDICES},
    **{k: "Commodities"  for k in COMMODITY_INDICES},
}


def simulate_market_overview() -> list[dict]:
    end    = datetime(2026, 2, 28)
    ytd_s  = datetime(2026, 1, 1)
    results = []
    for i, (name, (mu, sigma, p0, flow)) in enumerate(_INDEX_PARAMS.items()):
        prices = _gbm(p0, 400, mu, sigma, seed=i * 7)
        def ret(d0):
            w = prices[prices.index >= d0]
            if len(w) < 2:
                return np.nan
            return (w.iloc[-1] / w.iloc[0] - 1) * 100
        results.append({
            "name":       name,
            "category":   _CAT_MAP.get(name, "Equity"),
            "ticker":     name,
            "current":    float(prices.iloc[-1]),
            "return_3m":  ret(end - timedelta(days=90)),
            "return_6m":  ret(end - timedelta(days=180)),
            "return_ytd": ret(ytd_s),
            "return_1y":  ret(end - timedelta(days=365)),
            "flow_3m":    flow,
            "prices":     prices,
        })
    return results


# ── Section 2: Sector Analysis ─────────────────────────────────────────────────

_SECTOR_PARAMS = {
    "Info. Technology":    (0.22, 0.20, 380,  2_800),
    "Health Care":         (0.09, 0.13, 145,    750),
    "Financials":          (0.14, 0.14, 39,     680),
    "Cons. Discretionary": (0.12, 0.18, 188,    500),
    "Communication Svcs":  (0.18, 0.17, 85,     460),
    "Industrials":         (0.11, 0.13, 110,    430),
    "Consumer Staples":    (0.05, 0.09, 76,     420),
    "Energy":              (0.03, 0.20, 88,     370),
    "Utilities":           (0.04, 0.10, 68,     140),
    "Real Estate":         (0.06, 0.13, 40,     130),
    "Materials":           (0.07, 0.15, 84,     120),
}

# Per-ticker: (pe, d_ebitda, leverage, ytd_ret, 1m_ret, mktcap_B)
_TICKER_DATA = {
    "AAPL":  (29.5, 1.2, 1.8,  +3.2,  +1.1, 3_100),
    "MSFT":  (35.2, 0.8, 0.6,  +5.1,  +2.3, 3_050),
    "NVDA":  (55.0, 0.3, 0.1, +12.4,  +4.5, 3_200),
    "AVGO":  (28.1, 3.2, 2.1,  +6.8,  +1.8,  780),
    "ORCL":  (24.3, 4.8, 3.2,  +4.2,  +0.9,  450),
    "LLY":   (52.0, 1.8, 0.4,  +7.1,  +2.0,  780),
    "UNH":   (21.0, 2.1, 0.7,  +2.3,  +0.6,  470),
    "JNJ":   (15.5, 1.4, 0.5,  +1.8,  +0.3,  380),
    "ABBV":  (18.2, 3.5, 1.2,  +3.5,  +1.1,  310),
    "MRK":   (14.8, 1.2, 0.4,  +1.2,  -0.2,  280),
    "BRK-B": (22.0, np.nan, 0.3, +5.2, +1.5,  890),
    "JPM":   (12.8, np.nan, 1.4, +8.1, +2.2,  680),
    "V":     (32.0, 0.6, 1.1, +7.3,  +2.0,  520),
    "MA":    (35.5, 0.5, 1.0, +6.9,  +1.8,  465),
    "BAC":   (11.5, np.nan, 1.2, +4.3, +1.0,  330),
    "AMZN":  (45.0, 3.2, 0.6, +9.2,  +3.1,  2_100),
    "TSLA":  (80.0, 2.1, 0.2, -8.5,  -3.2,  700),
    "HD":    (22.0, 8.5, 4.2,  +3.8,  +0.9,  360),
    "BKNG":  (28.0, 2.8, 2.1, +5.2,  +1.6,  150),
    "NKE":   (35.0, 3.1, 1.4, -4.2,  -1.5,   88),
    "GOOGL": (22.0, 0.2, 0.1, +6.8,  +2.4,  2_200),
    "META":  (28.0, 0.1, 0.0, +8.1,  +3.2,  1_500),
    "NFLX":  (42.0, 1.8, 0.8, +7.3,  +2.5,  340),
    "DIS":   (38.0, 2.4, 0.9,  +2.1,  +0.4,  195),
    "T":     (11.0, 3.2, 1.8,  -1.5,  -0.5,   97),
    "GE":    (28.0, 1.5, 0.6, +6.2,  +2.1,  180),
    "CAT":   (17.0, 1.8, 1.2, +4.5,  +1.3,  155),
    "UNP":   (22.0, 2.8, 1.7,  +3.2,  +0.9,  145),
    "HON":   (24.0, 3.1, 1.5,  +2.8,  +0.7,  130),
    "RTX":   (38.0, 3.5, 1.3,  +5.1,  +1.8,  150),
    "WMT":   (30.0, 1.8, 0.9,  +4.3,  +1.2,  680),
    "PG":    (26.0, 2.2, 1.0,  +2.1,  +0.5,  380),
    "COST":  (52.0, 0.4, 0.3,  +5.8,  +1.9,  385),
    "KO":    (24.0, 3.8, 1.8,  +1.5,  +0.4,  270),
    "PEP":   (23.0, 3.5, 1.6,  +1.2,  +0.3,  235),
    "XOM":   (13.0, 0.8, 0.4,  +1.8,  -0.5,  480),
    "CVX":   (14.0, 1.1, 0.5,  +1.2,  -0.8,  300),
    "COP":   (12.0, 0.9, 0.6,  +0.8,  -1.2,  140),
    "EOG":   (11.5, 0.7, 0.4,  +0.5,  -0.9,   72),
    "SLB":   (18.0, 1.5, 0.8,  -2.1,  -1.0,   62),
    "NEE":   (22.0, 6.5, 1.5,  +3.2,  +0.8,  125),
    "SO":    (18.0, 5.8, 1.4,  +2.1,  +0.5,   80),
    "DUK":   (17.0, 6.2, 1.6,  +1.8,  +0.4,   72),
    "AEP":   (16.0, 5.5, 1.5,  +1.5,  +0.3,   50),
    "D":     (15.0, 6.0, 1.7,  +1.2,  +0.2,   45),
    "PLD":   (42.0, 8.5, 1.2,  +4.2,  +1.5,  115),
    "AMT":   (48.0,12.0, 2.1,  +2.8,  +0.8,   98),
    "EQIX":  (88.0,11.5, 1.8,  +3.5,  +1.2,   82),
    "PSA":   (28.0, 6.8, 1.0,  +1.5,  +0.4,   52),
    "O":     (52.0,10.5, 1.4,  +1.8,  +0.5,   48),
    "LIN":   (32.0, 2.5, 0.7,  +5.2,  +1.5,  220),
    "APD":   (28.0, 2.8, 0.8,  +3.2,  +0.9,   65),
    "SHW":   (32.0, 3.5, 2.1,  +4.5,  +1.3,   88),
    "FCX":   (15.0, 1.2, 0.8,  +8.5,  +3.2,   55),
    "NEM":   (18.0, 1.5, 0.4,  +9.1,  +3.5,   42),
}


def simulate_sector_data() -> list[dict]:
    end   = datetime(2026, 2, 28)
    ytd_s = datetime(2026, 1, 1)

    results = []
    for i, (sector_name, (mu, sigma, p0, aum)) in enumerate(_SECTOR_PARAMS.items()):
        prices = _gbm(p0, 400, mu, sigma, seed=i * 13 + 1)
        meta   = SECTORS[sector_name]

        def ret(d0, p=prices):
            w = p[p.index >= d0]
            return (w.iloc[-1] / w.iloc[0] - 1) * 100 if len(w) > 1 else np.nan

        tickers = []
        for sym in SECTOR_TICKERS.get(sector_name, []):
            td = _TICKER_DATA.get(sym, {})
            if isinstance(td, dict):
                continue
            pe, d_e, lev, r_ytd, r_1m, mc = td
            tickers.append({
                "ticker":     sym,
                "name":       sym,
                "market_cap": mc * 1e9,
                "return_ytd": r_ytd,
                "return_1m":  r_1m,
                "pe":         pe,
                "d_ebitda":   d_e,
                "leverage":   lev,
            })

        results.append({
            "sector":     sector_name,
            "etf":        meta["etf"],
            "color":      meta["color"],
            "return_ytd": ret(ytd_s),
            "return_3m":  ret(end - timedelta(days=90)),
            "return_1m":  ret(end - timedelta(days=30)),
            "aum":        aum,
            "tickers":    tickers,
        })

    results.sort(key=lambda x: x["aum"], reverse=True)
    return results


# ── Section 3: VIX ────────────────────────────────────────────────────────────

def simulate_vix_data() -> dict:
    """VIX with realistic mean-reversion around 16, spikes included."""
    n = 400
    end   = datetime(2026, 2, 27)   # last business day
    dates = pd.bdate_range(end=end, periods=n + 5)[-n:]

    # Mean-reverting VIX (Ornstein-Uhlenbeck)
    theta, mu_v, sigma_v = 0.18, 16.0, 3.5
    vix = [16.0]
    local_rng = np.random.default_rng(99)
    for _ in range(1, n):
        dv = theta * (mu_v - vix[-1]) + sigma_v * local_rng.normal()
        vix.append(max(9.0, vix[-1] + dv))

    # Inject a realistic spike ~6 months ago
    spike_idx = n - 130
    for j in range(10):
        vix[spike_idx + j] = min(vix[spike_idx + j] + 18 * np.exp(-j * 0.4), 55)

    prices = pd.Series(vix, index=dates)
    last_1y = prices[prices.index >= end - timedelta(days=365)]
    return {
        "prices":  prices,
        "current": float(prices.iloc[-1]),
        "mean_1y": float(last_1y.mean()),
        "max_1y":  float(last_1y.max()),
        "min_1y":  float(last_1y.min()),
        "pct25":   float(last_1y.quantile(0.25)),
        "pct75":   float(last_1y.quantile(0.75)),
    }


# ── Section 4 & 5: Macro ──────────────────────────────────────────────────────

def simulate_macro_data() -> dict:
    """
    5-year monthly macro series calibrated to realistic 2020-2026 dynamics:
      • CPI peaked ~9% mid-2022, disinflated to ~2.8% by Feb 2026
      • Unemployment trough ~3.4%, back up to ~4.1%
      • Payrolls strong, cooling late 2025
    """
    n_months = 72   # 6 years

    def _series(vals_tuple):
        """Build a pd.Series from explicit key-value list or GBM-like shape."""
        start_val, mu, sigma, trend, seed = vals_tuple
        return _macro_series(start_val, n_months, mu, sigma, trend, seed)

    # ── Inflation ──────────────────────────────────────────────────────────
    # CPI: rises to ~9% peak in month 28 (mid-2022), then disinflates
    cpi_level = _macro_series(258, n_months, 0.35, 0.15, 0.01, seed=1)
    cpi_yoy   = cpi_level.pct_change(12) * 100

    core_cpi_level = _macro_series(264, n_months, 0.28, 0.10, 0.008, seed=2)
    core_cpi_yoy   = core_cpi_level.pct_change(12) * 100

    pce_level = _macro_series(110, n_months, 0.25, 0.12, 0.008, seed=3)
    pce_yoy   = pce_level.pct_change(12) * 100

    core_pce_level = _macro_series(112, n_months, 0.22, 0.10, 0.007, seed=4)
    core_pce_yoy   = core_pce_level.pct_change(12) * 100

    ppi_level = _macro_series(120, n_months, 0.50, 0.30, 0.005, seed=5)
    ppi_yoy   = ppi_level.pct_change(12) * 100

    # 5Y Breakeven: range 2.0–2.7
    breakeven = _macro_series(2.15, n_months, 0.002, 0.04, 0.0, seed=6).clip(1.5, 3.5)

    inflation = {
        "CPI (Headline)":  cpi_yoy.dropna(),
        "CPI (Core)":      core_cpi_yoy.dropna(),
        "PCE":             pce_yoy.dropna(),
        "Core PCE":        core_pce_yoy.dropna(),
        "PPI (Final Dem)": ppi_yoy.dropna(),
        "5Y Breakeven":    breakeven.dropna(),
    }

    # ── Labor ─────────────────────────────────────────────────────────────
    # Unemployment: 3.4 trough → 4.1 now
    unemp = _macro_series(3.6, n_months, 0.01, 0.06, 0.003, seed=10).clip(3.0, 7.0)

    # NFP: monthly change in thousands – strong 2021-23, cooling
    payrolls_level = _macro_series(145_000, n_months, 150, 80, 5, seed=11)
    payrolls_mom   = payrolls_level.diff().dropna()

    # Job openings (JOLTS) – thousands, peaked ~12M, now ~8.5M
    jolts = _macro_series(7_000, n_months, 60, 200, 2, seed=12).clip(4_000, 13_000)

    # Initial claims (thousands, weekly-ish but stored monthly avg)
    claims = _macro_series(230, n_months, -0.3, 15, 0.2, seed=13).clip(180, 900)

    # LFPR
    lfpr = _macro_series(61.4, n_months, 0.02, 0.08, 0.005, seed=14).clip(59, 64)

    # Avg hourly earnings YoY
    ahe_level = _macro_series(28.0, n_months, 0.06, 0.05, 0.005, seed=15)
    ahe_yoy   = ahe_level.pct_change(12) * 100

    labor = {
        "Unemployment Rate":   unemp.dropna(),
        "Nonfarm Payrolls":    payrolls_mom.dropna(),
        "Job Openings":        jolts.dropna(),
        "Initial Claims":      claims.dropna(),
        "LFPR":                lfpr.dropna(),
        "Avg Hourly Earnings": ahe_yoy.dropna(),
    }

    return {"inflation": inflation, "labor": labor}
