"""
pdf_builder.py
--------------
Composes the multi-page PDF report.

Page structure (no VIX):
  1  – Market Overview
  2  – Equity Sector Analysis  (table + bar chart + analyst views)
  3…N – Sector ETF 10Y Charts  (2 per page, 6 pages for 11 sectors)
  N+1 – Inflation Indicators   (10Y, annotated)
  N+2 – Labor Market           (10Y, annotated)
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
from datetime import timedelta

from financial_report.config import (
    C, PAGE_W, PAGE_H, PAGE_DPI, REPORT_DATE,
    OUTPUT_PDF, OUTPUT_DIR, SECTOR_EVENTS,
)
from financial_report.charts import (
    draw_sparkline, draw_market_table, draw_sector_bars,
    draw_ticker_table, draw_macro_chart, draw_sector_history_chart,
    _val_color,
)

# ── Global matplotlib style ────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         8,
    "axes.facecolor":    C["surface"],
    "figure.facecolor":  C["bg"],
    "text.color":        C["text"],
    "axes.labelcolor":   C["text2"],
    "xtick.color":       C["text2"],
    "ytick.color":       C["text2"],
})


# ── Page skeleton factory ──────────────────────────────────────────────────────

def _new_page(section_title: str, description: str,
              subtitle: str = "") -> plt.Figure:
    fig = plt.figure(figsize=(PAGE_W, PAGE_H), dpi=PAGE_DPI)
    fig.patch.set_facecolor(C["bg"])

    # Header (top 7 %)
    ax_hdr = fig.add_axes([0, 0.93, 1, 0.07])
    ax_hdr.set_facecolor(C["primary"])
    ax_hdr.axis("off")
    ax_hdr.set_xlim(0, 1)
    ax_hdr.set_ylim(0, 1)

    ax_hdr.add_patch(mpatches.Rectangle(
        (0.012, 0.12), 0.006, 0.76,
        facecolor=C["accent"], transform=ax_hdr.transAxes,
        clip_on=False, zorder=3,
    ))
    ax_hdr.text(0.030, 0.80, "GLOBAL FINANCIAL MARKETS REPORT",
                fontsize=6, color="white", alpha=0.75,
                va="top", ha="left", transform=ax_hdr.transAxes)
    title_str = f"{section_title}   {subtitle}" if subtitle else section_title
    ax_hdr.text(0.030, 0.48, title_str,
                fontsize=15, fontweight="bold", color="white",
                va="center", ha="left", transform=ax_hdr.transAxes)
    ax_hdr.text(0.975, 0.5, REPORT_DATE.strftime("%B %d, %Y"),
                fontsize=9, color="white", alpha=0.85,
                va="center", ha="right", transform=ax_hdr.transAxes)

    # Footer (bottom 2.5 %)
    ax_ftr = fig.add_axes([0, 0, 1, 0.025])
    ax_ftr.set_facecolor(C["primary_dark"])
    ax_ftr.axis("off")
    ax_ftr.text(
        0.5, 0.5,
        "For informational purposes only. All data is simulated.  "
        "Sources: Yahoo Finance, FRED, BLS.",
        fontsize=5.8, color="white", alpha=0.80,
        ha="center", va="center", transform=ax_ftr.transAxes,
    )

    # Description band
    ax_desc = fig.add_axes([0.03, 0.875, 0.94, 0.048])
    ax_desc.set_facecolor(C["primary_bg"])
    ax_desc.axis("off")
    ax_desc.text(
        0.015, 0.5, description,
        fontsize=7.0, color=C["primary_dark"],
        va="center", ha="left", transform=ax_desc.transAxes,
        clip_on=True,
    )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Page 1 – Market Overview
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_market_overview(indices: list[dict]) -> plt.Figure:
    desc = (
        "Performance of major global benchmarks across equities, fixed income, and commodities. "
        "Returns over 3M, 6M, YTD, and 1Y.  "
        "Est. Flow is a 3-month buying-pressure proxy ($B).  "
        "Sparklines show full 10-year indexed price history."
    )
    fig = _new_page("Market Overview", desc)

    categories = ["Equity", "Fixed Income", "Commodities"]
    col_starts = [0.03, 0.36, 0.69]
    col_width  = 0.305

    for cat, x in zip(categories, col_starts):
        rows = [r for r in indices if r["category"] == cat]
        ax   = fig.add_axes([x, 0.32, col_width, 0.53])
        ax.set_facecolor(C["bg"])
        ax.axis("off")
        draw_market_table(ax, rows, cat)

    # Sparklines strip (full 10Y history)
    spark_y = 0.075
    spark_h = 0.20
    fig.text(0.03, spark_y + spark_h + 0.005, "Price History (10Y normalised)",
             fontsize=7.5, fontweight="bold", color=C["text"])

    n  = len(indices)
    sw = 0.94 / n if n > 0 else 0.1
    color_cycle = [
        C["blue"], C["red"], C["green"], C["orange"],
        C["purple"], C["teal"], C["cyan"], C["indigo"],
        C["pink"], C["deep_orange"], C["brown"], C["grey"],
        C["lime"], C["primary"], C["accent"], C["pos_light"],
        C["neg_light"], C["hint"],
    ]

    for i, row in enumerate(indices):
        ax_spark = fig.add_axes([0.03 + i * sw, spark_y, sw * 0.9, spark_h])
        prices = row.get("prices")
        col = color_cycle[i % len(color_cycle)]
        draw_sparkline(ax_spark, prices, col)
        fig.text(
            0.03 + i * sw + sw * 0.45, spark_y - 0.012,
            row["name"].split()[0],
            fontsize=5, ha="center", color=C["text2"],
        )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Page 2 – Sector Analysis (summary table + bar chart)
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_sector_analysis(sector_data: list[dict]) -> plt.Figure:
    desc = (
        "GICS sector performance (SPDR ETF proxies) ranked by YTD return.  "
        "Street Views = sell-side consensus as of report date.  "
        "B/H/S = # analyst Buy / Hold / Sell ratings.  AUM in $B."
    )
    fig = _new_page("Equity Sector Analysis", desc)

    # Bar chart (top portion)
    ax_bar = fig.add_axes([0.12, 0.535, 0.84, 0.32])
    draw_sector_bars(ax_bar, sector_data)

    # ── Sector summary table (middle) with analyst views ──────────────────
    ax_tbl = fig.add_axes([0.03, 0.28, 0.94, 0.24])
    ax_tbl.axis("off")
    ax_tbl.set_facecolor(C["bg"])

    headers = ["Sector", "ETF", "AUM", "YTD%", "3M%", "1M%", "Rating", "B / H / S"]
    widths  = [0.22,    0.055, 0.07, 0.08,  0.08,  0.08,  0.07,   0.14]
    row_h   = 1.0 / (len(sector_data) + 1)

    def _st(x, y, txt, ha="center", bold=False, color=C["text"], size=6.5):
        ax_tbl.text(x, y, txt, ha=ha, va="center", fontsize=size,
                    fontweight="bold" if bold else "normal",
                    color=color, transform=ax_tbl.transAxes, clip_on=False)

    def _sr(x, y, w, h, fc):
        ax_tbl.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="square,pad=0",
            facecolor=fc, edgecolor="none",
            transform=ax_tbl.transAxes, clip_on=False, zorder=1))

    # Header row
    _sr(0, 1 - row_h, 1, row_h, C["primary"])
    x = 0.0
    for hdr, w in zip(headers, widths):
        _st(x + w / 2, 1 - row_h / 2, hdr, bold=True, color="white", size=6.8)
        x += w

    for i, s in enumerate(sector_data):
        y = 1 - (i + 2) * row_h
        bg = C["surface"] if i % 2 == 0 else C["grid"]
        _sr(0, y, 1, row_h, bg)

        av     = s.get("analyst_views", {})
        rating = av.get("rating", "—")
        buys   = av.get("buys",   "—")
        holds  = av.get("holds",  "—")
        sells  = av.get("sells",  "—")
        bhs    = f"{buys} / {holds} / {sells}"

        rating_color = (
            C["pos_light"]  if rating == "OW" else
            C["neg_light"]  if rating == "UW" else
            C["text2"]
        )

        vals = [
            s["sector"],
            s["etf"],
            f"{s['aum']:.0f}",
            f"{s['return_ytd']:+.1f}%" if pd.notna(s["return_ytd"]) else "—",
            f"{s['return_3m']:+.1f}%"  if pd.notna(s["return_3m"])  else "—",
            f"{s['return_1m']:+.1f}%"  if pd.notna(s["return_1m"])  else "—",
            rating,
            bhs,
        ]
        fcs = [
            C["text"], C["text2"], C["text"],
            _val_color(s.get("return_ytd")),
            _val_color(s.get("return_3m")),
            _val_color(s.get("return_1m")),
            rating_color,
            C["text2"],
        ]
        x = 0.0
        for j, (val, w, fc) in enumerate(zip(vals, widths, fcs)):
            ha = "left" if j == 0 else "center"
            xp = x + (0.01 if j == 0 else w / 2)
            _st(xp, y + row_h / 2, val, ha=ha, color=fc, size=6.3)
            x += w

    # ── Top-ticker fundamental tables (bottom) ────────────────────────────
    cols, rows_count = 3, 3
    tw = 0.30
    th = 0.060
    t_left = 0.03
    t_bot  = 0.032

    for idx, sector in enumerate(sector_data[:cols * rows_count]):
        col_i = idx % cols
        row_i = idx // cols
        x = t_left + col_i * (tw + 0.02)
        y = t_bot + (rows_count - 1 - row_i) * (th + 0.012)
        ax_tk = fig.add_axes([x, y, tw, th])
        ax_tk.set_facecolor(C["bg"])
        top_ticker = sector["tickers"][:1]
        draw_ticker_table(ax_tk, top_ticker, sector["sector"])

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Pages 3–8 – Sector ETF 10Y History Charts (2 per page)
# ═══════════════════════════════════════════════════════════════════════════════

def build_pages_sector_history(sector_data: list[dict]) -> list[plt.Figure]:
    """
    Returns one figure per pair of sectors (2 charts per page).
    Each chart shows 10Y indexed price history with SMA, ATH/Low markers,
    and key event vertical bar annotations.
    """
    pages = []
    pairs = [sector_data[i:i+2] for i in range(0, len(sector_data), 2)]
    total = len(pairs)

    for page_num, pair in enumerate(pairs, start=1):
        desc = (
            "10-year indexed price history (100 = Feb 2016).  "
            "Dashed = 50d SMA,  dash-dot = 200d SMA.  "
            "Green bar = period ATH,  red bar = period low.  "
            "Dotted verticals mark key market events."
        )
        subtitle = f"({page_num}/{total})"
        fig = _new_page("Sector ETF  —  10-Year History", desc, subtitle=subtitle)

        y_positions = [0.505, 0.065]   # top chart, bottom chart
        chart_h = 0.40

        for chart_idx, sector in enumerate(pair):
            y = y_positions[chart_idx]
            ax = fig.add_axes([0.07, y, 0.89, chart_h])
            events = SECTOR_EVENTS.get(sector["sector"], [])
            draw_sector_history_chart(
                ax,
                prices=sector.get("prices"),
                sector_name=sector["sector"],
                etf_name=sector["etf"],
                color=sector["color"],
                events=events,
            )

        pages.append(fig)

    return pages


# ═══════════════════════════════════════════════════════════════════════════════
# Inflation page
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_inflation(macro: dict) -> plt.Figure:
    desc = (
        "Year-over-year % change for key US inflation gauges, 10-year history.  "
        "Dashed amber = Fed 2% Core PCE target.  "
        "Shaded pink regions mark key stress / disinflationary turning points.  "
        "Dashed grey = 12-month rolling average."
    )
    fig = _new_page("Inflation Indicators", desc)

    inflation = macro.get("inflation", {})
    series_cfg = [
        ("CPI (Headline)",  C["blue"],   2.0,  "YoY %"),
        ("CPI (Core)",      C["indigo"], 2.0,  "YoY %"),
        ("PCE",             C["teal"],   2.0,  "YoY %"),
        ("Core PCE",        C["green"],  2.0,  "YoY %"),
        ("PPI (Final Dem)", C["orange"], None, "YoY %"),
        ("5Y Breakeven",    C["purple"], 2.0,  "Rate %"),
    ]

    grid_cols, grid_rows = 3, 2
    cw, ch   = 0.285, 0.34
    left0    = 0.05
    bot0     = 0.05
    gap_x    = 0.04
    gap_y    = 0.06

    for idx, (key, col, ref, ylabel) in enumerate(series_cfg):
        ci = idx % grid_cols
        ri = idx // grid_cols
        x  = left0 + ci * (cw + gap_x)
        y  = bot0 + (grid_rows - 1 - ri) * (ch + gap_y)
        ax = fig.add_axes([x, y, cw, ch])
        draw_macro_chart(ax, inflation.get(key), title=key,
                         ylabel=ylabel, ref_line=ref, color=col)

    fig.text(
        0.05, 0.028,
        "† Shaded = stress periods: Fed tightening (Q4-2018), COVID (2020), "
        "Rate hike cycle (2022), SVB crisis (2023).  "
        "Dashed amber = Fed 2% target.",
        fontsize=6.2, color=C["text2"], style="italic",
    )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Labor Market page
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_labor(macro: dict) -> plt.Figure:
    desc = (
        "Key US labor market indicators, 10-year history.  "
        "Nonfarm Payrolls = monthly change (000s).  "
        "Avg Hourly Earnings = YoY %.  All other series shown as levels.  "
        "Shaded regions mark key macro stress events."
    )
    fig = _new_page("Labor Market Indicators", desc)

    labor = macro.get("labor", {})
    series_cfg = [
        ("Unemployment Rate",   C["red"],    None, "Rate %"),
        ("Nonfarm Payrolls",    C["blue"],   None, "MoM Chg (000s)"),
        ("Job Openings",        C["teal"],   None, "000s"),
        ("Initial Claims",      C["orange"], None, "000s"),
        ("LFPR",                C["purple"], None, "Rate %"),
        ("Avg Hourly Earnings", C["indigo"], None, "YoY %"),
    ]

    grid_cols, grid_rows = 3, 2
    cw, ch = 0.285, 0.34
    left0  = 0.05
    bot0   = 0.05
    gap_x  = 0.04
    gap_y  = 0.06

    for idx, (key, col, ref, ylabel) in enumerate(series_cfg):
        ci = idx % grid_cols
        ri = idx // grid_cols
        x  = left0 + ci * (cw + gap_x)
        y  = bot0 + (grid_rows - 1 - ri) * (ch + gap_y)
        ax = fig.add_axes([x, y, cw, ch])
        draw_macro_chart(ax, labor.get(key), title=key,
                         ylabel=ylabel, ref_line=ref, color=col)

    fig.text(
        0.05, 0.028,
        "† Shaded = stress periods: Fed tightening (Q4-2018), COVID (2020), "
        "Rate hike cycle (2022), SVB crisis (2023).",
        fontsize=6.2, color=C["text2"], style="italic",
    )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# PDF assembler
# ═══════════════════════════════════════════════════════════════════════════════

def assemble_report(pages: list[plt.Figure]) -> str:
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_PDF)
    with PdfPages(output_path) as pdf:
        for fig in pages:
            pdf.savefig(fig, bbox_inches="tight", dpi=PAGE_DPI)
            plt.close(fig)
    print(f"\n  PDF saved → {output_path}")
    return output_path
