"""
data_fetcher.py
---------------
All data-acquisition logic for the financial report.

Sources:
  - yfinance   : equity/bond/commodity prices, sector ETFs, VIX, ticker fundamentals
  - FRED        : macro indicators (via pandas_datareader or direct HTTP)
  - BLS v1 API  : fallback for unemployment / payrolls (no key required)

Every public function returns plain Python dicts / pandas Series so that
chart-drawing code never has to touch raw API objects.
"""

import warnings
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

from financial_report.config import (
    REPORT_DATE, EQUITY_INDICES, BOND_INDICES, COMMODITY_INDICES,
    SECTORS, SECTOR_TICKERS, INFLATION_SERIES, LABOR_SERIES,
)

warnings.filterwarnings("ignore")

# ── Helpers ────────────────────────────────────────────────────────────────────

def _ytd_start():
    return datetime(REPORT_DATE.year, 1, 1)


def _pct_return(series: pd.Series, start: datetime, end: datetime) -> float:
    """Return % change between the first available price on/after `start`
    and the last available price on/before `end`."""
    try:
        window = series.loc[start:end].dropna()
        if len(window) < 2:
            return np.nan
        return (window.iloc[-1] / window.iloc[0] - 1) * 100
    except Exception:
        return np.nan


def _fetch_prices(ticker: str, start: datetime, end: datetime) -> pd.Series | None:
    """Download daily close prices for a single ticker."""
    try:
        raw = yf.download(
            ticker, start=start, end=end + timedelta(days=1),
            progress=False, auto_adjust=True, actions=False,
        )
        if raw.empty:
            return None
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close.index = pd.to_datetime(close.index).tz_localize(None)
        return close.dropna()
    except Exception as e:
        print(f"  [warn] {ticker}: {e}")
        return None


def _flow_proxy(ticker: str, start: datetime, end: datetime) -> float:
    """
    Estimate net-flow direction using ETF dollar-volume on up vs down days.
    Positive  → net buying pressure   (billions USD)
    Negative  → net selling pressure  (billions USD)
    """
    try:
        raw = yf.download(
            ticker, start=start, end=end + timedelta(days=1),
            progress=False, auto_adjust=True, actions=False,
        )
        if raw.empty:
            return np.nan
        close  = raw["Close"].squeeze()
        volume = raw["Volume"].squeeze()
        change = close.pct_change()
        flow   = (volume * close * np.sign(change)).sum()
        return float(flow / 1e9)
    except Exception:
        return np.nan


# ── Section 1 : Market Overview ───────────────────────────────────────────────

def fetch_market_overview() -> list[dict]:
    """
    Returns a list of dicts – one per index – with returns and flow proxy:
      name, category, current, return_3m, return_6m, return_ytd, return_1y,
      flow_3m (est. $B), prices (pd.Series for sparkline)
    """
    end   = REPORT_DATE
    start = end - timedelta(days=400)       # enough buffer for all periods

    all_indices = {
        "Equity":       EQUITY_INDICES,
        "Fixed Income": BOND_INDICES,
        "Commodities":  COMMODITY_INDICES,
    }

    results = []
    for category, index_map in all_indices.items():
        for name, meta in index_map.items():
            ticker = meta["ticker"]
            etf    = meta["etf"]
            print(f"  Fetching {name} ({ticker}) …")

            prices = _fetch_prices(ticker, start, end)
            if prices is None or len(prices) < 5:
                continue

            flow = _flow_proxy(etf, end - timedelta(days=90), end)

            results.append({
                "name":        name,
                "category":    category,
                "ticker":      ticker,
                "current":     float(prices.iloc[-1]),
                "return_3m":   _pct_return(prices, end - timedelta(days=90),  end),
                "return_6m":   _pct_return(prices, end - timedelta(days=180), end),
                "return_ytd":  _pct_return(prices, _ytd_start(),              end),
                "return_1y":   _pct_return(prices, end - timedelta(days=365), end),
                "flow_3m":     flow,
                "prices":      prices,
            })
    return results


# ── Section 2 : Sector Analysis ───────────────────────────────────────────────

def fetch_sector_data() -> list[dict]:
    """
    Returns a list of sector dicts sorted by ETF total-assets (descending):
      sector, etf, color, return_ytd, return_3m, return_1m, aum,
      tickers: list of ticker dicts (name, return_ytd, return_1m, pe, d_ebitda, leverage)
    """
    end      = REPORT_DATE
    start    = end - timedelta(days=400)
    ytd      = _ytd_start()

    # Bulk price download for all ETFs + tickers at once
    etf_tickers = [v["etf"] for v in SECTORS.values()]
    all_tickers = list({t for tlist in SECTOR_TICKERS.values() for t in tlist})
    print(f"  Bulk downloading {len(etf_tickers) + len(all_tickers)} tickers …")

    bulk_prices = {}
    try:
        raw = yf.download(
            etf_tickers + all_tickers,
            start=start, end=end + timedelta(days=1),
            progress=False, auto_adjust=True, actions=False, group_by="ticker",
        )
        for sym in etf_tickers + all_tickers:
            try:
                s = raw[sym]["Close"].dropna()
                s.index = pd.to_datetime(s.index).tz_localize(None)
                if len(s) > 5:
                    bulk_prices[sym] = s
            except Exception:
                pass
    except Exception as e:
        print(f"  [warn] bulk download: {e}")

    sector_results = []
    for sector_name, meta in SECTORS.items():
        etf   = meta["etf"]
        color = meta["color"]

        prices = bulk_prices.get(etf)
        r_ytd  = _pct_return(prices, ytd, end)              if prices is not None else np.nan
        r_3m   = _pct_return(prices, end-timedelta(90), end) if prices is not None else np.nan
        r_1m   = _pct_return(prices, end-timedelta(30), end) if prices is not None else np.nan

        # AUM from ETF info
        aum = np.nan
        try:
            info = yf.Ticker(etf).info
            aum  = info.get("totalAssets", np.nan)
            if aum:
                aum = aum / 1e9   # → billions
        except Exception:
            pass

        # Top-ticker fundamentals
        ticker_rows = []
        for sym in SECTOR_TICKERS.get(sector_name, []):
            p = bulk_prices.get(sym)
            try:
                info       = yf.Ticker(sym).fast_info
                mktcap     = getattr(info, "market_cap", np.nan)
                last_price = getattr(info, "last_price", np.nan)
            except Exception:
                mktcap = last_price = np.nan

            try:
                full_info  = yf.Ticker(sym).info
                pe         = full_info.get("trailingPE", np.nan)
                total_debt = full_info.get("totalDebt",  np.nan)
                ebitda     = full_info.get("ebitda",     np.nan)
                dte        = full_info.get("debtToEquity", np.nan)
                short_name = full_info.get("shortName", sym)
            except Exception:
                pe = total_debt = ebitda = dte = np.nan
                short_name = sym

            d_ebitda = (
                float(total_debt) / float(ebitda)
                if pd.notna(total_debt) and pd.notna(ebitda) and ebitda != 0
                else np.nan
            )
            leverage = float(dte) / 100 if pd.notna(dte) else np.nan

            ticker_rows.append({
                "ticker":     sym,
                "name":       short_name[:22],
                "market_cap": mktcap,
                "return_ytd": _pct_return(p, ytd, end)               if p is not None else np.nan,
                "return_1m":  _pct_return(p, end-timedelta(30), end) if p is not None else np.nan,
                "pe":         pe,
                "d_ebitda":   d_ebitda,
                "leverage":   leverage,
            })

        sector_results.append({
            "sector":     sector_name,
            "etf":        etf,
            "color":      color,
            "return_ytd": r_ytd,
            "return_3m":  r_3m,
            "return_1m":  r_1m,
            "aum":        aum,
            "tickers":    ticker_rows,
        })

    # Sort by AUM descending
    sector_results.sort(
        key=lambda x: x["aum"] if pd.notna(x["aum"]) else 0,
        reverse=True,
    )
    return sector_results


# ── Section 3 : VIX ───────────────────────────────────────────────────────────

def fetch_vix_data() -> dict | None:
    """
    Returns:
      prices (pd.Series, 1Y daily), current, mean_1y, max_1y, min_1y,
      pct25, pct75
    """
    end   = REPORT_DATE
    start = end - timedelta(days=400)
    print("  Fetching VIX …")
    prices = _fetch_prices("^VIX", start, end)
    if prices is None:
        return None
    last_year = prices[prices.index >= end - timedelta(days=365)]
    return {
        "prices":  prices,
        "current": float(prices.iloc[-1]),
        "mean_1y": float(last_year.mean()),
        "max_1y":  float(last_year.max()),
        "min_1y":  float(last_year.min()),
        "pct25":   float(last_year.quantile(0.25)),
        "pct75":   float(last_year.quantile(0.75)),
    }


# ── Section 4 : Macro ─────────────────────────────────────────────────────────

def _fred_series(series_id: str, start: datetime, end: datetime) -> pd.Series | None:
    """Fetch a FRED series via pandas_datareader."""
    try:
        import pandas_datareader.data as web
        df = web.DataReader(series_id, "fred", start, end)
        s  = df.iloc[:, 0].dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        return s
    except Exception as e:
        print(f"  [warn] FRED {series_id}: {e}")
        return None


def _bls_series(series_id: str, start_year: int, end_year: int) -> pd.Series | None:
    """Fetch a BLS monthly series using the public v1 API (no key needed)."""
    try:
        url  = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
        body = {"seriesid": [series_id],
                "startyear": str(start_year),
                "endyear":   str(end_year)}
        resp = requests.post(url, json=body, timeout=15)
        data = resp.json()
        if data.get("status") != "REQUEST_SUCCEEDED":
            return None
        rows = []
        for item in data["Results"]["series"][0]["data"]:
            period = item["period"]
            if period.startswith("M"):
                dt  = datetime(int(item["year"]), int(period[1:]), 1)
                val = float(item["value"])
                rows.append((dt, val))
        if not rows:
            return None
        s = pd.Series(dict(rows)).sort_index()
        s.index = pd.to_datetime(s.index)
        return s
    except Exception as e:
        print(f"  [warn] BLS {series_id}: {e}")
        return None


def fetch_macro_data() -> dict:
    """
    Returns a dict:
      "inflation" → {label: pd.Series of YoY % (or level for breakeven)}
      "labor"     → {label: pd.Series (level or MoM)}
    """
    end   = REPORT_DATE
    start = end - timedelta(days=365 * 6)   # 6 years of history

    macro = {"inflation": {}, "labor": {}}

    # ── Inflation ──────────────────────────────────────────────────────────────
    print("  Fetching inflation series …")
    for label, sid in INFLATION_SERIES.items():
        s = _fred_series(sid, start, end)
        if s is not None and len(s) > 12:
            if label == "5Y Breakeven":
                macro["inflation"][label] = s          # already a rate
            else:
                macro["inflation"][label] = s.pct_change(12) * 100   # YoY %
        else:
            macro["inflation"][label] = None

    # ── Labor ──────────────────────────────────────────────────────────────────
    print("  Fetching labor series …")
    for label, sid in LABOR_SERIES.items():
        s = _fred_series(sid, start, end)

        # Fallback to BLS for unemployment / payrolls / LFPR
        if s is None:
            bls_map = {
                "Unemployment Rate":   "LNS14000000",
                "Nonfarm Payrolls":    "CES0000000001",
                "LFPR":                "LNS11300000",
                "Initial Claims":      "LNS14000000",   # rough fallback
            }
            if label in bls_map:
                s = _bls_series(bls_map[label], start.year, end.year)

        if s is not None:
            if label == "Nonfarm Payrolls":
                macro["labor"][label] = s.diff().dropna()      # MoM change (thousands)
            elif label == "Avg Hourly Earnings":
                macro["labor"][label] = s.pct_change(12) * 100 # YoY %
            else:
                macro["labor"][label] = s
        else:
            macro["labor"][label] = None

    return macro
