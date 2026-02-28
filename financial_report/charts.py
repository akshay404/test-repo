"""
charts.py
---------
Reusable chart-drawing helpers.

Every function receives a matplotlib Axes object and data, and draws onto it
in place.  Nothing here creates figures or saves files – that is the job of
pdf_builder.py.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from datetime import datetime, timedelta

from financial_report.config import C, REPORT_DATE, MACRO_STRESS_EVENTS


# ── Shared style helpers ───────────────────────────────────────────────────────

def _style_axes(ax, title="", xlabel="", ylabel="", grid=True):
    """Apply consistent base style to any axes."""
    ax.set_facecolor(C["surface"])
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(C["divider"])
    if grid:
        ax.yaxis.grid(True, color=C["grid"], linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
    if title:
        ax.set_title(title, fontsize=8, fontweight="bold",
                     color=C["text"], pad=4, loc="left")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=7, color=C["text2"])
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=7, color=C["text2"])
    ax.tick_params(labelsize=6.5, colors=C["text2"])


def _val_color(v) -> str:
    if pd.isna(v):
        return C["hint"]
    return C["pos_light"] if v >= 0 else C["neg_light"]


def _fmt(v, decimals=2, suffix="") -> str:
    if pd.isna(v):
        return "—"
    return f"{v:+.{decimals}f}{suffix}"


# ── Sparkline ─────────────────────────────────────────────────────────────────

def draw_sparkline(ax, prices: pd.Series, color: str):
    """Tiny borderless sparkline of normalised price history (full length)."""
    ax.axis("off")
    if prices is None or len(prices) < 3:
        ax.text(0.5, 0.5, "N/A", ha="center", va="center",
                fontsize=6, color=C["hint"], transform=ax.transAxes)
        return
    norm = (prices / prices.iloc[0] - 1) * 100
    ax.plot(norm.values, color=color, linewidth=1.2, solid_capstyle="round")
    ax.fill_between(range(len(norm)), norm.values, alpha=0.15, color=color)
    ax.set_xlim(0, len(norm) - 1)


# ── Market overview table ─────────────────────────────────────────────────────

def draw_market_table(ax, rows: list[dict], category_label: str):
    """
    Render a styled performance table for one asset category.
    Columns: Name | 3M | 6M | YTD | 1Y | Est.Flow($B)
    """
    ax.axis("off")
    col_labels = ["", "3M", "6M", "YTD", "1Y", "Flow($B)"]
    col_widths = [0.34, 0.11, 0.11, 0.11, 0.11, 0.15]
    n_rows = len(rows)
    row_h  = 1.0 / (n_rows + 2)

    def _rect(x, y, w, h, fc, ec="none", alpha=1.0):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="square,pad=0",
            facecolor=fc, edgecolor=ec, linewidth=0.4,
            transform=ax.transAxes, clip_on=False, zorder=2, alpha=alpha,
        ))

    def _text(x, y, txt, ha="center", color=C["text"], bold=False, size=7.5):
        ax.text(x, y, txt, ha=ha, va="center", fontsize=size,
                fontweight="bold" if bold else "normal",
                color=color, transform=ax.transAxes, clip_on=False, zorder=3)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # Category header
    _rect(0, 1 - row_h, 1, row_h, fc=C["primary"])
    _text(0.03, 1 - row_h / 2, category_label.upper(),
          ha="left", color="white", bold=True, size=7.5)

    # Column headers
    y_col = 1 - 2 * row_h
    _rect(0, y_col, 1, row_h, fc=C["primary_bg"])
    x_cursor = 0.0
    for label, w in zip(col_labels, col_widths):
        _text(x_cursor + w / 2, y_col + row_h / 2, label,
              color=C["primary_dark"], bold=True, size=6.5)
        x_cursor += w

    # Data rows
    for i, row in enumerate(rows):
        y = 1 - (i + 3) * row_h
        bg = C["surface"] if i % 2 == 0 else C["grid"]
        _rect(0, y, 1, row_h, fc=bg)

        cols_data = [
            row.get("name", ""),
            _fmt(row.get("return_3m"),  suffix="%"),
            _fmt(row.get("return_6m"),  suffix="%"),
            _fmt(row.get("return_ytd"), suffix="%"),
            _fmt(row.get("return_1y"),  suffix="%"),
            _fmt(row.get("flow_3m"), decimals=1),
        ]
        col_colors = [
            C["text"],
            _val_color(row.get("return_3m")),
            _val_color(row.get("return_6m")),
            _val_color(row.get("return_ytd")),
            _val_color(row.get("return_1y")),
            _val_color(row.get("flow_3m")),
        ]
        x_cursor = 0.0
        for j, (val, w, fc) in enumerate(zip(cols_data, col_widths, col_colors)):
            ha = "left" if j == 0 else "center"
            xpos = x_cursor + (0.02 if j == 0 else w / 2)
            _text(xpos, y + row_h / 2, val, ha=ha, color=fc, size=7)
            x_cursor += w


# ── Sector horizontal bar chart ───────────────────────────────────────────────

def draw_sector_bars(ax, sector_data: list[dict]):
    """Horizontal bar chart of sector YTD and 3M returns, sorted by YTD."""
    _style_axes(ax, grid=False)

    names   = [s["sector"] for s in sector_data]
    ytd     = [s["return_ytd"] for s in sector_data]
    r3m     = [s["return_3m"]  for s in sector_data]
    colors  = [s["color"]      for s in sector_data]

    y = np.arange(len(names))
    bar_h = 0.35

    order  = np.argsort([v if not np.isnan(v) else -999 for v in ytd])
    names  = [names[i]  for i in order]
    ytd    = [ytd[i]    for i in order]
    r3m    = [r3m[i]    for i in order]
    colors = [colors[i] for i in order]

    bars_ytd = ax.barh(y + bar_h / 2, ytd, height=bar_h, label="YTD",
                       color=[_val_color(v) for v in ytd], alpha=0.9, zorder=3)
    bars_3m  = ax.barh(y - bar_h / 2, r3m, height=bar_h, label="3M",
                       color=[_val_color(v) for v in r3m], alpha=0.55, zorder=3)

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=7, color=C["text"])
    ax.axvline(0, color=C["divider"], linewidth=0.8)
    ax.xaxis.grid(True, color=C["grid"], linewidth=0.5)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.1f}%"))
    ax.set_xlabel("Return (%)", fontsize=7, color=C["text2"])
    ax.tick_params(axis="x", labelsize=6.5)

    for bar, val in zip(bars_ytd, ytd):
        if not np.isnan(val):
            ax.text(bar.get_width() + (0.15 if val >= 0 else -0.15),
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:+.1f}%", va="center",
                    ha="left" if val >= 0 else "right",
                    fontsize=6, color=C["text2"])

    ax.legend(handles=[bars_ytd, bars_3m], fontsize=6.5, frameon=False,
              loc="lower right")
    ax.set_title("Sector Performance — YTD vs 3M", fontsize=8,
                 fontweight="bold", color=C["text"], loc="left", pad=4)


# ── Sector / ticker fundamental table ────────────────────────────────────────

def draw_ticker_table(ax, rows: list[dict], sector_name: str):
    """Mini table: Ticker | YTD% | 1M% | P/E | D/EBITDA | Leverage"""
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    headers = ["Ticker", "YTD%", "1M%", "P/E", "D/EBITDA", "Lev.(D/E)"]
    widths  = [0.14,     0.11,   0.11,  0.12,  0.14,       0.12]

    n = len(rows)
    row_h = 1.0 / (n + 2)

    def _rect(x, y, w, h, fc):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="square,pad=0",
            facecolor=fc, edgecolor="none",
            transform=ax.transAxes, clip_on=False, zorder=2,
        ))

    def _text(x, y, txt, ha="center", color=C["text"], bold=False, size=6.5):
        ax.text(x, y, txt, ha=ha, va="center", fontsize=size,
                fontweight="bold" if bold else "normal",
                color=color, transform=ax.transAxes, clip_on=False, zorder=3)

    _rect(0, 1 - row_h, 1, row_h, C["primary_bg"])
    _text(0.01, 1 - row_h / 2, sector_name, ha="left",
          color=C["primary_dark"], bold=True, size=7)

    _rect(0, 1 - 2 * row_h, 1, row_h, C["grid"])
    x_c = 0.0
    for hdr, w in zip(headers, widths):
        _text(x_c + w / 2, 1 - 1.5 * row_h, hdr,
              color=C["text2"], bold=True, size=6)
        x_c += w
    _text(sum(widths) + (1 - sum(widths)) / 2,
          1 - 1.5 * row_h, "Name", color=C["text2"], bold=True, size=6)

    for i, row in enumerate(rows):
        y = 1 - (i + 3) * row_h
        _rect(0, y, 1, row_h, C["surface"] if i % 2 == 0 else C["grid"])

        vals = [
            row.get("ticker", ""),
            _fmt(row.get("return_ytd"), suffix="%"),
            _fmt(row.get("return_1m"),  suffix="%"),
            _fmt(row.get("pe"),  decimals=1) if not pd.isna(row.get("pe", np.nan)) else "—",
            _fmt(row.get("d_ebitda"), decimals=1) if not pd.isna(row.get("d_ebitda", np.nan)) else "—",
            _fmt(row.get("leverage"),  decimals=2) if not pd.isna(row.get("leverage", np.nan)) else "—",
        ]
        fcs = [
            C["primary_light"],
            _val_color(row.get("return_ytd")),
            _val_color(row.get("return_1m")),
            C["text"], C["text"], C["text"],
        ]
        x_c = 0.0
        for val, w, fc in zip(vals, widths, fcs):
            _text(x_c + w / 2, y + row_h / 2, val, color=fc, size=6.5)
            x_c += w
        name_w = 1 - sum(widths)
        _text(x_c + 0.01, y + row_h / 2, row.get("name", ""),
              ha="left", color=C["text2"], size=6)


# ── 10Y Sector ETF history chart ──────────────────────────────────────────────

def draw_sector_history_chart(ax, prices: pd.Series, sector_name: str,
                               etf_name: str, color: str, events=None):
    """
    Full 10Y history chart for a sector ETF.
    Shows:
      • Indexed price line (100 = start)
      • 50-day and 200-day SMA
      • Vertical bar at the period ATH (green) and period Low (red)
      • Vertical dashed bars at key historical events with brief labels
    """
    if prices is None or len(prices) < 20:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                fontsize=9, color=C["hint"], transform=ax.transAxes)
        return

    _style_axes(ax, ylabel="Indexed Price  (100 = start)", xlabel="Year")

    # Normalize to 100
    norm = prices / prices.iloc[0] * 100

    # Price line
    ax.plot(norm.index, norm.values, color=color, linewidth=1.5,
            zorder=3, label="Price", solid_capstyle="round")
    ax.fill_between(norm.index, norm.values, 100,
                    where=(norm.values >= 100), alpha=0.10, color=color, zorder=1)
    ax.fill_between(norm.index, norm.values, 100,
                    where=(norm.values < 100), alpha=0.08, color=C["neg"], zorder=1)

    # SMAs
    sma50  = norm.rolling(50).mean()
    sma200 = norm.rolling(200).mean()
    ax.plot(sma50.index, sma50.values, color=C["accent"],
            linewidth=1.0, linestyle="--", zorder=4, label="50d SMA", alpha=0.9)
    ax.plot(sma200.index, sma200.values, color=C["hint"],
            linewidth=1.1, linestyle="-.", zorder=4, label="200d SMA", alpha=0.9)

    # ATH and period low
    hi_idx = norm.idxmax()
    lo_idx = norm.idxmin()
    hi_val = norm.max()
    lo_val = norm.min()

    ax.axvline(hi_idx, color=C["pos"], linewidth=1.2, linestyle="--",
               alpha=0.8, zorder=5)
    ax.annotate(
        f"ATH\n{hi_val:.0f}",
        xy=(hi_idx, hi_val),
        xytext=(6, 0), textcoords="offset points",
        fontsize=6.5, color=C["pos"], fontweight="bold", va="center",
        arrowprops=dict(arrowstyle="-", color=C["pos"], lw=0.5),
    )

    ax.axvline(lo_idx, color=C["neg"], linewidth=1.2, linestyle="--",
               alpha=0.8, zorder=5)
    ax.annotate(
        f"Low\n{lo_val:.0f}",
        xy=(lo_idx, lo_val),
        xytext=(6, 0), textcoords="offset points",
        fontsize=6.5, color=C["neg"], fontweight="bold", va="center",
        arrowprops=dict(arrowstyle="-", color=C["neg"], lw=0.5),
    )

    # Key event vertical bars
    ymin, ymax = norm.min() * 0.96, norm.max() * 1.04
    if events:
        y_text = ymin + (ymax - ymin) * 0.52   # mid-chart
        for date, label in events:
            ts = pd.Timestamp(date)
            if norm.index[0] <= ts <= norm.index[-1]:
                ax.axvline(ts, color=C["primary_dark"], linewidth=0.7,
                           linestyle=":", alpha=0.55, zorder=4)
                ax.text(
                    ts, y_text, label,
                    fontsize=5.8, color=C["primary_dark"],
                    ha="center", va="center", rotation=90, alpha=0.80,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                              alpha=0.65, edgecolor="none"),
                )

    ax.set_ylim(ymin, ymax)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.tick_params(axis="x", rotation=0, labelsize=7)
    ax.tick_params(axis="y", labelsize=7)

    # Legend top-left
    ax.legend(fontsize=7, frameon=False, loc="upper left", ncol=3)
    ax.set_title(f"{sector_name}   ({etf_name})",
                 fontsize=10, fontweight="bold", color=C["text"], pad=6, loc="left")


# ── VIX line chart ─────────────────────────────────────────────────────────────

def draw_vix_chart(ax, prices: pd.Series, vix_stats: dict,
                   cutoff_days: int | None = None, title: str = ""):
    end   = REPORT_DATE
    start = (end - timedelta(days=cutoff_days)) if cutoff_days else prices.index[0]
    data  = prices[prices.index >= start].copy()

    _style_axes(ax, title=title, ylabel="VIX Level", xlabel="Date")

    ax.axhspan(0,  15, alpha=0.07, color=C["green"],  zorder=0)
    ax.axhspan(15, 25, alpha=0.07, color=C["orange"], zorder=0)
    ax.axhspan(25, 40, alpha=0.07, color=C["red"],    zorder=0)
    ax.axhspan(40, 90, alpha=0.07, color=C["purple"], zorder=0)

    ax.plot(data.index, data.values, color=C["primary_light"],
            linewidth=1.2, zorder=3)
    ax.fill_between(data.index, data.values, alpha=0.12,
                    color=C["primary_light"], zorder=2)

    current = float(data.iloc[-1])
    ax.axhline(current, color=C["accent"], linewidth=0.8,
               linestyle="--", zorder=4)
    ax.text(data.index[-1], current + 0.5, f"  {current:.1f}",
            fontsize=6.5, color=C["accent"], va="bottom", zorder=5)

    mean = float(vix_stats["mean_1y"])
    ax.axhline(mean, color=C["hint"], linewidth=0.6, linestyle=":", zorder=3)

    ax.set_ylim(bottom=max(0, data.min() - 2))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.tick_params(axis="x", rotation=20)

    for label, mid, col in [
        ("Low",      7.5, C["green"]),
        ("Moderate", 20,  C["orange"]),
        ("Elevated", 32.5,C["red"]),
    ]:
        if ax.get_ylim()[1] > mid:
            ax.text(data.index[-1], mid, f" {label}",
                    fontsize=5.5, color=col, va="center", alpha=0.7)


# ── Macro mini-chart ──────────────────────────────────────────────────────────

def draw_macro_chart(ax, series: pd.Series | None, title: str,
                     ylabel: str = "", ref_line: float | None = None,
                     color: str = None, stress_events=None):
    """
    10-year line chart for a single macro indicator.

    Features:
      • Shaded stress event regions with brief labels
      • Optional reference line (e.g. Fed 2% target)
      • Annotated latest value
      • Proper x / y axis labels
    """
    _style_axes(ax, title=title, ylabel=ylabel)

    if series is None or len(series.dropna()) < 4:
        ax.text(0.5, 0.5, "Data unavailable", ha="center", va="center",
                fontsize=7, color=C["hint"], transform=ax.transAxes)
        return

    end   = REPORT_DATE
    start = end - timedelta(days=365 * 10)
    s     = series[series.index >= start].dropna()

    col = color or C["primary_light"]
    ax.plot(s.index, s.values, color=col, linewidth=1.4, zorder=3)
    ax.fill_between(s.index, s.values, alpha=0.10, color=col, zorder=2)

    # 12-month rolling average (equivalent of SMA for monthly macro data)
    if len(s) >= 12:
        sma12 = s.rolling(12).mean()
        ax.plot(sma12.index, sma12.values, color=C["hint"],
                linewidth=0.9, linestyle="--", zorder=4, alpha=0.85,
                label="12m avg")

    # Reference line (e.g. Fed 2% inflation target)
    if ref_line is not None:
        ax.axhline(ref_line, color=C["accent"], linewidth=0.9,
                   linestyle="--", zorder=5, label=f"Target {ref_line}%")

    # Annotate latest value
    latest = float(s.iloc[-1])
    ax.annotate(
        f"{latest:.2f}",
        xy=(s.index[-1], latest),
        xytext=(5, 0), textcoords="offset points",
        fontsize=7, color=col, va="center", fontweight="bold",
    )

    # Stress event shading + vertical lines
    use_events = stress_events if stress_events is not None else MACRO_STRESS_EVENTS
    if use_events and len(s) > 0:
        ymin_v, ymax_v = s.min(), s.max()
        pad = (ymax_v - ymin_v) * 0.08 if ymax_v != ymin_v else 0.2
        y_lbl = ymax_v + pad * 0.3

        for ev_start, ev_end, label in use_events:
            ts0 = pd.Timestamp(ev_start)
            ts1 = pd.Timestamp(ev_end)
            if ts0 > s.index[-1] or ts1 < s.index[0]:
                continue
            # Shade the region
            ax.axvspan(ts0, ts1, alpha=0.13, color=C["neg"], zorder=1)
            # Vertical line at start
            ax.axvline(ts0, color=C["neg"], linewidth=0.6,
                       linestyle=":", alpha=0.55, zorder=4)
            # Brief label at top of the shaded area
            mid_ts = ts0 + (ts1 - ts0) / 2
            ax.text(
                mid_ts, y_lbl, label,
                fontsize=5.0, color=C["neg_light"],
                ha="center", va="bottom", rotation=0,
                style="italic", alpha=0.85,
                clip_on=True,
            )

    # Axis formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.tick_params(axis="x", rotation=0, labelsize=6.5)
    ax.tick_params(axis="y", labelsize=6.5)
    ax.set_xlabel("Year", fontsize=6.5, color=C["text2"])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}"))

    # Legend if we have reference or SMA lines
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, labels, fontsize=5.5, frameon=False,
                  loc="upper left", ncol=len(handles))
