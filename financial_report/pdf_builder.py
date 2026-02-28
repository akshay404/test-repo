"""
pdf_builder.py
--------------
Composes the five-page PDF report using matplotlib's PdfPages backend.

Each page is a full matplotlib Figure (8.5 × 11 in, portrait).
Material design is applied at the figure level:
  • A solid primary-blue header bar (logo mark + title + date)
  • A dark footer bar (disclaimer)
  • White "card" panels for content areas

Pages produced:
  1 – Market Overview         (equity / fixed income / commodities tables)
  2 – Sector Analysis         (bar chart + top-ticker fundamentals)
  3 – VIX / Volatility        (multi-period charts + stats ribbon)
  4 – Inflation Indicators    (2×3 grid of macro mini-charts)
  5 – Labor Market            (2×3 grid of macro mini-charts)
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

from financial_report.config import C, PAGE_W, PAGE_H, PAGE_DPI, REPORT_DATE, OUTPUT_PDF, OUTPUT_DIR
from financial_report.charts import (
    draw_sparkline, draw_market_table, draw_sector_bars,
    draw_ticker_table, draw_vix_chart, draw_macro_chart,
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

def _new_page(section_title: str, description: str) -> plt.Figure:
    """
    Create a blank portrait figure with:
      - Blue header bar (brand mark + section title + report date)
      - Grey footer bar (disclaimer)
      - Description text block beneath the header

    Returns the Figure. Caller then adds content axes via fig.add_axes().
    """
    fig = plt.figure(figsize=(PAGE_W, PAGE_H), dpi=PAGE_DPI)
    fig.patch.set_facecolor(C["bg"])

    # ── Header (top 7 % of page) ────────────────────────────────────────────
    ax_hdr = fig.add_axes([0, 0.93, 1, 0.07])
    ax_hdr.set_facecolor(C["primary"])
    ax_hdr.axis("off")
    ax_hdr.set_xlim(0, 1)
    ax_hdr.set_ylim(0, 1)

    # Accent left stripe
    ax_hdr.add_patch(mpatches.Rectangle(
        (0.012, 0.12), 0.006, 0.76,
        facecolor=C["accent"], transform=ax_hdr.transAxes,
        clip_on=False, zorder=3,
    ))
    # Report brand (small)
    ax_hdr.text(0.030, 0.80, "GLOBAL FINANCIAL MARKETS REPORT",
                fontsize=6, color="white", alpha=0.75,
                va="top", ha="left", transform=ax_hdr.transAxes)
    # Section title (large)
    ax_hdr.text(0.030, 0.48, section_title,
                fontsize=15, fontweight="bold", color="white",
                va="center", ha="left", transform=ax_hdr.transAxes)
    # Date (right)
    ax_hdr.text(0.975, 0.5, REPORT_DATE.strftime("%B %d, %Y"),
                fontsize=9, color="white", alpha=0.85,
                va="center", ha="right", transform=ax_hdr.transAxes)

    # ── Footer (bottom 2.5 %) ──────────────────────────────────────────────
    ax_ftr = fig.add_axes([0, 0, 1, 0.025])
    ax_ftr.set_facecolor(C["primary_dark"])
    ax_ftr.axis("off")
    ax_ftr.text(
        0.5, 0.5,
        "For informational purposes only. Est. Flows are a volume/price-based proxy, not official fund-flow data.  "
        "Sources: Yahoo Finance, FRED, BLS.",
        fontsize=5.8, color="white", alpha=0.80,
        ha="center", va="center", transform=ax_ftr.transAxes,
    )

    # ── Description band (just below header) ───────────────────────────────
    ax_desc = fig.add_axes([0.03, 0.875, 0.94, 0.048])
    ax_desc.set_facecolor(C["primary_bg"])
    ax_desc.axis("off")
    ax_desc.text(
        0.015, 0.5, description,
        fontsize=7.5, color=C["primary_dark"],
        va="center", ha="left", transform=ax_desc.transAxes,
        wrap=True,
    )

    return fig


def _card(fig, left, bottom, width, height, title=""):
    """Add a white card with optional bold title label above it."""
    ax = fig.add_axes([left, bottom, width, height])
    ax.set_facecolor(C["surface"])
    for spine in ax.spines.values():
        spine.set_color(C["divider"])
        spine.set_linewidth(0.5)
    ax.set_xticks([])
    ax.set_yticks([])
    if title:
        fig.text(left, bottom + height + 0.005, title,
                 fontsize=7.5, fontweight="bold", color=C["text"])
    return ax


# ═══════════════════════════════════════════════════════════════════════════════
# Page 1 – Market Overview
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_market_overview(indices: list[dict]) -> plt.Figure:
    desc = (
        "Performance of major global benchmarks across equities, fixed income, and commodities. "
        "Returns shown over 3-month, 6-month, year-to-date, and 1-year horizons.  "
        "Est. Flow is a 3-month buying-pressure proxy (volume × price × sign(return), $B)."
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

    # ── Sparklines strip (bottom band) ────────────────────────────────────
    spark_y = 0.075
    spark_h = 0.20
    fig.text(0.03, spark_y + spark_h + 0.005, "Price History (1Y normalised)",
             fontsize=7.5, fontweight="bold", color=C["text"])

    n  = len(indices)
    sw = (0.94) / n if n > 0 else 0.1
    color_cycle = [C["blue"], C["red"], C["green"], C["orange"],
                   C["purple"], C["teal"], C["cyan"], C["indigo"],
                   C["pink"], C["deep_orange"], C["brown"], C["grey"],
                   C["lime"], C["primary"], C["accent"], C["pos_light"],
                   C["neg_light"], C["hint"]]

    end   = REPORT_DATE
    start = end - timedelta(days=365)

    for i, row in enumerate(indices):
        ax_spark = fig.add_axes([0.03 + i * sw, spark_y, sw * 0.9, spark_h])
        prices = row.get("prices")
        if prices is not None:
            prices = prices[prices.index >= start]
        col = color_cycle[i % len(color_cycle)]
        draw_sparkline(ax_spark, prices, col)
        fig.text(
            0.03 + i * sw + sw * 0.45, spark_y - 0.012,
            row["name"].split()[0],
            fontsize=5, ha="center", color=C["text2"],
        )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Page 2 – Sector Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_sector_analysis(sector_data: list[dict]) -> plt.Figure:
    desc = (
        "GICS sector performance ranked by YTD and 3-month return (SPDR ETF proxies). "
        "Fundamental metrics (P/E, D/EBITDA, Leverage) shown for the top market-cap "
        "ticker within each sector.  AUM figures in $B."
    )
    fig = _new_page("Equity Sector Analysis", desc)

    # ── Bar chart (top portion) ────────────────────────────────────────────
    ax_bar = fig.add_axes([0.12, 0.54, 0.84, 0.33])
    draw_sector_bars(ax_bar, sector_data)

    # ── Sector summary table (middle) ──────────────────────────────────────
    ax_tbl = fig.add_axes([0.03, 0.36, 0.94, 0.165])
    ax_tbl.axis("off")
    ax_tbl.set_facecolor(C["bg"])

    headers = ["Sector", "ETF", "AUM($B)", "YTD%", "3M%", "1M%"]
    widths  = [0.26, 0.07, 0.10, 0.11, 0.11, 0.11]
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
        _st(x + w / 2, 1 - row_h / 2, hdr, bold=True, color="white", size=7)
        x += w

    for i, s in enumerate(sector_data):
        y = 1 - (i + 2) * row_h
        bg = C["surface"] if i % 2 == 0 else C["grid"]
        _sr(0, y, 1, row_h, bg)

        vals = [
            s["sector"],
            s["etf"],
            f"{s['aum']:.1f}" if pd.notna(s["aum"]) else "—",
            f"{s['return_ytd']:+.2f}%" if pd.notna(s["return_ytd"]) else "—",
            f"{s['return_3m']:+.2f}%"  if pd.notna(s["return_3m"])  else "—",
            f"{s['return_1m']:+.2f}%"  if pd.notna(s["return_1m"])  else "—",
        ]
        fcs = [
            C["text"], C["text2"], C["text"],
            (C["pos_light"] if pd.notna(s["return_ytd"]) and s["return_ytd"] >= 0 else C["neg_light"])
            if pd.notna(s["return_ytd"]) else C["hint"],
            (C["pos_light"] if pd.notna(s["return_3m"]) and s["return_3m"] >= 0 else C["neg_light"])
            if pd.notna(s["return_3m"]) else C["hint"],
            (C["pos_light"] if pd.notna(s["return_1m"]) and s["return_1m"] >= 0 else C["neg_light"])
            if pd.notna(s["return_1m"]) else C["hint"],
        ]
        x = 0.0
        for j, (val, w, fc) in enumerate(zip(vals, widths, fcs)):
            ha = "left" if j == 0 else "center"
            xp = x + (0.01 if j == 0 else w / 2)
            _st(xp, y + row_h / 2, val, ha=ha, color=fc, size=6.5)
            x += w

    # ── Top-ticker fundamental tables (bottom grid) ────────────────────────
    # 3 columns × 4 rows  (we have 11 sectors, show first 12)
    cols, rows_count = 3, 4
    tw = 0.30
    th = 0.068
    t_left = 0.03
    t_bot  = 0.027

    for idx, sector in enumerate(sector_data[:cols * rows_count]):
        col_i = idx % cols
        row_i = idx // cols
        x = t_left + col_i * (tw + 0.02)
        y = t_bot + (rows_count - 1 - row_i) * (th + 0.01)
        ax_tk = fig.add_axes([x, y, tw, th])
        ax_tk.set_facecolor(C["bg"])
        top_ticker = sector["tickers"][:1]   # one row per sector for space
        draw_ticker_table(ax_tk, top_ticker, sector["sector"])

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Page 3 – VIX / Volatility
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_vix(vix: dict | None) -> plt.Figure:
    desc = (
        "CBOE Volatility Index (VIX) measures the 30-day implied volatility of S&P 500 options. "
        "Regimes: Low (<15), Moderate (15–25), Elevated (25–35), Extreme (>35).  "
        "Dashed line = current level; dotted line = 1-year mean."
    )
    fig = _new_page("Volatility Monitor — VIX", desc)

    if vix is None:
        fig.text(0.5, 0.5, "VIX data unavailable",
                 ha="center", va="center", fontsize=14, color=C["hint"])
        return fig

    # ── Stats ribbon ──────────────────────────────────────────────────────
    stats = [
        ("Current", f"{vix['current']:.1f}",  C["accent"]),
        ("1Y Mean", f"{vix['mean_1y']:.1f}",   C["primary_light"]),
        ("1Y High", f"{vix['max_1y']:.1f}",    C["neg_light"]),
        ("1Y Low",  f"{vix['min_1y']:.1f}",    C["pos_light"]),
        ("25th %ile", f"{vix['pct25']:.1f}",   C["text2"]),
        ("75th %ile", f"{vix['pct75']:.1f}",   C["text2"]),
    ]
    ribbon_y = 0.845
    bw = 0.94 / len(stats)
    for i, (label, val, col) in enumerate(stats):
        x = 0.03 + i * bw
        ax_s = fig.add_axes([x, ribbon_y, bw * 0.92, 0.05])
        ax_s.set_facecolor(C["surface"])
        for sp in ax_s.spines.values():
            sp.set_color(C["divider"])
            sp.set_linewidth(0.4)
        ax_s.axis("off")
        ax_s.text(0.5, 0.75, label, ha="center", va="center",
                  fontsize=6, color=C["text2"], transform=ax_s.transAxes)
        ax_s.text(0.5, 0.28, val, ha="center", va="center",
                  fontsize=13, fontweight="bold", color=col,
                  transform=ax_s.transAxes)

    # ── Main 1Y chart ─────────────────────────────────────────────────────
    ax_main = fig.add_axes([0.08, 0.50, 0.88, 0.32])
    draw_vix_chart(ax_main, vix["prices"], vix,
                   cutoff_days=365, title="VIX — 1-Year")

    # ── Period charts (3M, 6M, YTD) ───────────────────────────────────────
    periods = [
        ("3M",  90,                                "VIX — 3 Months"),
        ("6M",  180,                               "VIX — 6 Months"),
        ("YTD", (REPORT_DATE - REPORT_DATE.replace(month=1, day=1)).days + 1,
                                                   "VIX — Year to Date"),
    ]
    pw, ph = 0.27, 0.22
    pb = 0.07
    for j, (_, days, title) in enumerate(periods):
        ax_p = fig.add_axes([0.05 + j * 0.32, pb, pw, ph])
        draw_vix_chart(ax_p, vix["prices"], vix, cutoff_days=days, title=title)

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Page 4 – Inflation
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_inflation(macro: dict) -> plt.Figure:
    desc = (
        "Year-over-year % change for key US inflation gauges.  The Federal Reserve targets 2% "
        "Core PCE (dashed amber line).  PPI leads consumer prices by 3–6 months.  "
        "5-Year Breakeven reflects bond-market inflation expectations."
    )
    fig = _new_page("Inflation Indicators", desc)

    inflation = macro.get("inflation", {})
    series_cfg = [
        ("CPI (Headline)",  C["blue"],        2.0,  "YoY %"),
        ("CPI (Core)",      C["indigo"],      2.0,  "YoY %"),
        ("PCE",             C["teal"],        2.0,  "YoY %"),
        ("Core PCE",        C["green"],       2.0,  "YoY %"),
        ("PPI (Final Dem)", C["orange"],      None, "YoY %"),
        ("5Y Breakeven",    C["purple"],      2.0,  "Rate %"),
    ]

    grid_cols, grid_rows = 3, 2
    cw, ch = 0.285, 0.30
    left0, bot0 = 0.05, 0.40
    gap_x, gap_y = 0.04, 0.07

    for idx, (key, col, ref, ylabel) in enumerate(series_cfg):
        ci = idx % grid_cols
        ri = idx // grid_cols
        x = left0 + ci * (cw + gap_x)
        y = bot0 + (grid_rows - 1 - ri) * (ch + gap_y)
        ax = fig.add_axes([x, y, cw, ch])
        draw_macro_chart(ax, inflation.get(key), title=key,
                         ylabel=ylabel, ref_line=ref, color=col)

    # Annotation footnote
    fig.text(0.05, 0.365, "† Dashed amber line = Fed 2% target (Core PCE is the Fed's preferred gauge)",
             fontsize=6.5, color=C["text2"], style="italic")

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Page 5 – Labor Market
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_labor(macro: dict) -> plt.Figure:
    desc = (
        "Key US labor market indicators over 5 years.  Nonfarm Payrolls shown as monthly change (000s).  "
        "Avg Hourly Earnings is YoY %.  All other series shown as levels.  "
        "Shaded periods reflect cyclical turning points."
    )
    fig = _new_page("Labor Market Indicators", desc)

    labor = macro.get("labor", {})
    series_cfg = [
        ("Unemployment Rate",   C["red"],         None, "Rate %"),
        ("Nonfarm Payrolls",    C["blue"],         None, "MoM Chg (000s)"),
        ("Job Openings",        C["teal"],         None, "000s"),
        ("Initial Claims",      C["orange"],       None, "000s"),
        ("LFPR",                C["purple"],       None, "Rate %"),
        ("Avg Hourly Earnings", C["indigo"],       None, "YoY %"),
    ]

    grid_cols, grid_rows = 3, 2
    cw, ch = 0.285, 0.30
    left0, bot0 = 0.05, 0.40
    gap_x, gap_y = 0.04, 0.07

    for idx, (key, col, ref, ylabel) in enumerate(series_cfg):
        ci = idx % grid_cols
        ri = idx // grid_cols
        x = left0 + ci * (cw + gap_x)
        y = bot0 + (grid_rows - 1 - ri) * (ch + gap_y)
        ax = fig.add_axes([x, y, cw, ch])
        draw_macro_chart(ax, labor.get(key), title=key,
                         ylabel=ylabel, ref_line=ref, color=col)

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# PDF assembler
# ═══════════════════════════════════════════════════════════════════════════════

def assemble_report(pages: list[plt.Figure]) -> str:
    """Save all figure pages into a single PDF and return the file path."""
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_PDF)
    with PdfPages(output_path) as pdf:
        for fig in pages:
            pdf.savefig(fig, bbox_inches="tight", dpi=PAGE_DPI)
            plt.close(fig)
    print(f"\n  PDF saved → {output_path}")
    return output_path
