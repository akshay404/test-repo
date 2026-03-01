"""
pdf_builder.py
--------------
Composes the multi-page PDF report.

Page structure:
  1    – Market Overview  (detailed 2-row mini-charts with SMA/ATH/Low)
  2    – Equity Sector Analysis  (table + bar chart + analyst views)
  3…13 – Sector ETF 10Y Charts  (1 per page, top/bottom-5 performers table)
  14–15 – Inflation Indicators  (3 charts + macro summary per page)
  16–17 – Labor Market          (3 charts + macro summary per page)
"""

import os
import textwrap
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
    draw_index_mini_chart, draw_sector_performers_table,
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _wrap_text(text: str, max_chars: int = 110) -> str:
    """Word-wrap text to max_chars per line, returning a newline-joined string."""
    return "\n".join(textwrap.wrap(text, max_chars))


def _generate_macro_bullets(series_data: list, section: str) -> tuple:
    """
    Generate (bullets, commentary) for a macro summary panel.

    series_data : list of (key, pd.Series | None)
    section     : "inflation" or "labor"
    Returns     : (list[str] bullets, str commentary)
    """
    bullets = []

    for key, s in series_data:
        if s is None or s.dropna().empty:
            bullets.append(f"• {key}: Data unavailable.")
            continue
        sc     = s.dropna()
        latest = float(sc.iloc[-1])
        prev6  = float(sc.iloc[-6])  if len(sc) >= 6  else latest
        prev12 = float(sc.iloc[-12]) if len(sc) >= 12 else latest
        chg6   = latest - prev6
        trend  = ("rising" if chg6 > 0.15 else
                  "falling" if chg6 < -0.15 else "stable")

        if section == "inflation":
            vs2    = latest - 2.0
            tgt    = f"{abs(vs2):.1f}pp {'above' if vs2 > 0 else 'below'} the 2% target"
            if key == "5Y Breakeven":
                anchor = ("anchored near" if 1.8 < latest < 2.5 else
                          "above" if latest >= 2.5 else "below")
                bullets.append(
                    f"• {key}: {latest:.2f}%  —  Market-implied 5-year avg inflation; "
                    f"{anchor} the 2% target. Long-run expectations remain "
                    f"{'well-anchored' if 1.8 < latest < 2.5 else 'elevated'}."
                )
            else:
                bullets.append(
                    f"• {key}: {latest:.1f}% YoY  —  {trend.capitalize()} from "
                    f"{prev6:.1f}% six months ago; currently {tgt}."
                )

        else:  # labor
            if key == "Nonfarm Payrolls":
                strength = ("strong" if latest > 180 else
                            "moderate" if latest > 80 else "weak")
                bullets.append(
                    f"• {key}: {latest:+.0f}K MoM  —  Latest monthly job creation; "
                    f"{strength} pace relative to the ~100–150K breakeven rate."
                )
            elif key == "Job Openings":
                demand = "robust" if latest > 8_000 else "normalizing"
                bullets.append(
                    f"• {key}: {latest / 1_000:.1f}M  —  JOLTS openings; "
                    f"{demand} labor demand ({latest / 1_000:.1f}M vs ~7M pre-pandemic)."
                )
            elif key == "Initial Claims":
                state = ("historically tight" if latest < 250 else
                         "moderating" if latest < 350 else "elevated")
                bullets.append(
                    f"• {key}: {latest:.0f}K wkly  —  Weekly UI filings; "
                    f"{state} — {'layoffs remain restrained' if latest < 250 else 'labor conditions softening'}."
                )
            elif key == "LFPR":
                vs_pre = latest - 63.4  # pre-pandemic peak ~63.4%
                bullets.append(
                    f"• {key}: {latest:.1f}%  —  Share of civilians in the labor force; "
                    f"{abs(vs_pre):.1f}pp {'above' if vs_pre > 0 else 'below'} the pre-pandemic peak of ~63.4%."
                )
            elif key == "Avg Hourly Earnings":
                pressure = ("elevated, sustaining consumer spending" if latest > 4.0 else
                            "easing toward pre-pandemic norms (~3%)")
                bullets.append(
                    f"• {key}: {latest:.1f}% YoY  —  Wage growth {pressure}; "
                    f"{'still contributing to sticky services inflation' if latest > 4.0 else 'less inflationary pressure from wages'}."
                )
            else:  # Unemployment Rate
                cycle = ("historically tight" if latest < 4.0 else
                         "normalizing from cycle lows" if latest < 4.5 else "rising")
                bullets.append(
                    f"• {key}: {latest:.1f}%  —  {cycle.capitalize()}; "
                    f"{'above' if latest > 4.0 else 'near'} the Fed's estimated long-run rate of ~4.0%."
                )

    # Broader commentary
    if section == "inflation":
        lead_s = series_data[0][1]
        v0 = float(lead_s.dropna().iloc[-1]) if (lead_s is not None and not lead_s.dropna().empty) else 3.0
        if v0 > 4.0:
            commentary = (
                "Policy Outlook:  Inflation remains meaningfully above target. The Federal Reserve "
                "is likely to maintain a restrictive stance, keeping rates elevated until sustained "
                "disinflation is evident across multiple core gauges."
            )
        elif v0 > 2.8:
            commentary = (
                "Policy Outlook:  Disinflation is progressing, but the 'last mile' to 2% has proven "
                "sticky — particularly in services. The Fed remains data-dependent; rate cuts are "
                "contingent on durable progress in Core PCE and resilient labor conditions."
            )
        elif v0 > 2.0:
            commentary = (
                "Policy Outlook:  Inflation is nearing the 2% target. The FOMC may begin cautious "
                "easing if disinflation continues, though members will want several confirming "
                "data points before committing to a rate-cut path."
            )
        else:
            commentary = (
                "Policy Outlook:  Inflation has returned to or below target. The balance of risks "
                "has shifted toward supporting growth. Rate cuts may accelerate if disinflationary "
                "momentum continues or labor conditions soften materially."
            )
    else:
        unemp_s = next((s for k, s in series_data if "Unemployment" in k), None)
        u = float(unemp_s.dropna().iloc[-1]) if (unemp_s is not None and not unemp_s.dropna().empty) else 4.1
        if u < 4.0:
            commentary = (
                f"Labor Market Outlook:  At {u:.1f}% unemployment the labor market remains historically "
                "tight. The Fed sees limited need for emergency stimulus; robust wage growth continues "
                "to underpin consumer spending and support GDP resilience."
            )
        elif u < 4.8:
            commentary = (
                f"Labor Market Outlook:  Unemployment at {u:.1f}% signals a healthy but moderating "
                "labor market. Payroll growth has cooled from post-pandemic peaks, gradually easing "
                "wage pressures. The FOMC is watching for further softening that might justify "
                "accelerating the pace of rate cuts."
            )
        else:
            commentary = (
                f"Labor Market Outlook:  Unemployment at {u:.1f}% represents a meaningful rise from "
                "cycle lows, signalling demand-side cooling. The Fed may pivot more aggressively toward "
                "easing to prevent further deterioration in employment conditions."
            )

    return bullets, commentary


def _draw_macro_summary_panel(fig, bullets: list, commentary: str,
                               section_title: str, rect: list):
    """
    Render a styled analytical summary panel onto the figure.

    rect : [x0, y0, width, height] in figure coordinates.
    """
    ax = fig.add_axes(rect)
    ax.set_facecolor(C["primary_bg"])
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # Left accent bar
    ax.add_patch(mpatches.Rectangle(
        (0, 0), 0.006, 1.0, facecolor=C["primary"],
        transform=ax.transAxes, clip_on=True, zorder=3,
    ))

    # Section header
    ax.text(0.016, 0.93,
            f"MACRO ANALYSIS  —  {section_title.upper()}",
            fontsize=7.5, fontweight="bold", color=C["primary_dark"],
            va="top", ha="left", transform=ax.transAxes)

    # Thin separator
    ax.axhline(0.82, color=C["divider"], linewidth=0.6, xmin=0.01, xmax=0.99)

    # Bullet points – evenly spaced in the 0.78→0.22 band
    n   = max(len(bullets), 1)
    top = 0.78
    bot = 0.24
    spc = (top - bot) / n
    for i, bullet in enumerate(bullets):
        ax.text(0.016, top - i * spc, bullet,
                fontsize=6.8, color=C["text"],
                va="top", ha="left", transform=ax.transAxes, clip_on=True)

    # Thin separator above commentary
    ax.axhline(0.20, color=C["divider"], linewidth=0.6, xmin=0.01, xmax=0.99)

    # Commentary (italic, wrapped)
    wrapped = _wrap_text(commentary, max_chars=118)
    ax.text(0.016, 0.17, wrapped,
            fontsize=6.5, color=C["text2"], style="italic",
            va="top", ha="left", transform=ax.transAxes,
            clip_on=True, linespacing=1.45)


# ═══════════════════════════════════════════════════════════════════════════════
# Page 1 – Market Overview
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_market_overview(indices: list) -> plt.Figure:
    desc = (
        "Performance of major global benchmarks across equities, fixed income, and commodities.  "
        "Returns over 3M, 6M, YTD, and 1Y.  Est. Flow = 3-month buying-pressure proxy ($B).  "
        "Lower panels: 10Y indexed history with 50d SMA (amber ‐‐), 200d SMA (grey ‐·‐), "
        "ATH (green |) and period Low (red |) markers."
    )
    fig = _new_page("Market Overview", desc)

    # ── Category tables (upper two-thirds) ──────────────────────────────────
    categories = ["Equity", "Fixed Income", "Commodities"]
    col_starts = [0.03, 0.36, 0.69]
    col_width  = 0.305

    for cat, x in zip(categories, col_starts):
        rows = [r for r in indices if r["category"] == cat]
        ax   = fig.add_axes([x, 0.32, col_width, 0.53])
        ax.set_facecolor(C["bg"])
        ax.axis("off")
        draw_market_table(ax, rows, cat)

    # ── Detailed mini-charts (lower third, 2 rows of 9) ─────────────────────
    n      = len(indices)
    n_cols = 9
    sw     = 0.94 / n_cols          # width slot per chart
    cw     = sw * 0.91              # actual chart width (small gap)
    row1_y = 0.168                  # top of row-1 charts (indices 0–8)
    row2_y = 0.038                  # top of row-2 charts (indices 9–17)
    ch     = 0.118                  # chart height (both rows)

    # Section label + mini-legend
    label_y = 0.300
    fig.text(0.03, label_y, "10-Year Indexed Price History",
             fontsize=7.5, fontweight="bold", color=C["text"])
    fig.text(0.97, label_y,
             "— Amber = 50d SMA    –·– Grey = 200d SMA    | Green = ATH    | Red = Low",
             fontsize=5.2, color=C["text2"], ha="right")

    color_cycle = [
        C["blue"], C["red"], C["green"], C["orange"],
        C["purple"], C["teal"], C["cyan"], C["indigo"],
        C["pink"], C["deep_orange"], C["brown"], C["grey"],
        C["lime"], C["primary"], C["accent"], C["pos_light"],
        C["neg_light"], C["hint"],
    ]

    for i, row in enumerate(indices):
        col_i = i % n_cols
        row_i = i // n_cols
        x_pos = 0.03 + col_i * sw
        y_pos = row1_y if row_i == 0 else row2_y
        ax_m  = fig.add_axes([x_pos, y_pos, cw, ch])
        col   = color_cycle[i % len(color_cycle)]
        draw_index_mini_chart(
            ax_m,
            prices=row.get("prices"),
            color=col,
            name=row["name"],
            return_ytd=row.get("return_ytd"),
        )

    # Row category labels (left-side badges)
    for row_y, label in [(row1_y + ch / 2, "Equities"), (row2_y + ch / 2, "Fixed Inc. & Cmdty")]:
        fig.text(0.005, row_y, label, fontsize=5.0, color=C["text2"],
                 rotation=90, ha="center", va="center")

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Page 2 – Sector Analysis (summary table + bar chart)
# ═══════════════════════════════════════════════════════════════════════════════

def build_page_sector_analysis(sector_data: list) -> plt.Figure:
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
        y  = 1 - (i + 2) * row_h
        bg = C["surface"] if i % 2 == 0 else C["grid"]
        _sr(0, y, 1, row_h, bg)

        av     = s.get("analyst_views", {})
        rating = av.get("rating", "—")
        buys   = av.get("buys",   "—")
        holds  = av.get("holds",  "—")
        sells  = av.get("sells",  "—")
        bhs    = f"{buys} / {holds} / {sells}"

        rating_color = (
            C["pos_light"] if rating == "OW" else
            C["neg_light"] if rating == "UW" else
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
# Pages 3–13 – Sector ETF 10Y History Charts (1 per page)
# ═══════════════════════════════════════════════════════════════════════════════

def build_pages_sector_history(sector_data: list) -> list:
    """
    Returns one figure per sector (1 chart per page).

    Each page shows:
      • Full-width 10Y indexed price history chart with SMA, ATH/Low, event labels
      • Below the chart: a split Top-5 / Bottom-5 constituent performers table
    """
    pages = []
    total = len(sector_data)

    for page_num, sector in enumerate(sector_data, start=1):
        desc = (
            "10-year indexed price history (100 = Feb 2016).  "
            "Dashed = 50d SMA,  dash-dot = 200d SMA.  "
            "Green bar = period ATH,  red bar = period low.  "
            "Dotted verticals = key market events.  "
            "Tables below: top 5 and bottom 5 YTD performers within the sector."
        )
        subtitle = f"({page_num}/{total})"
        fig = _new_page("Sector ETF  —  10-Year History", desc, subtitle=subtitle)

        # ── History chart (upper portion) ────────────────────────────────
        ax_chart = fig.add_axes([0.07, 0.50, 0.89, 0.36])
        events   = SECTOR_EVENTS.get(sector["sector"], [])
        draw_sector_history_chart(
            ax_chart,
            prices=sector.get("prices"),
            sector_name=sector["sector"],
            etf_name=sector["etf"],
            color=sector["color"],
            events=events,
        )

        # ── Performers section label ──────────────────────────────────────
        fig.text(
            0.03, 0.478,
            "Constituent Performance  —  YTD Return",
            fontsize=8, fontweight="bold", color=C["text"],
        )
        fig.text(
            0.97, 0.478,
            f"Top 10 holdings by index weight  ·  Source: simulated",
            fontsize=6, color=C["text2"], ha="right",
        )

        # ── Top/Bottom 5 performers table (lower portion) ────────────────
        ax_perf = fig.add_axes([0.03, 0.068, 0.94, 0.40])
        draw_sector_performers_table(ax_perf, sector.get("tickers", []))

        pages.append(fig)

    return pages


# ═══════════════════════════════════════════════════════════════════════════════
# Inflation pages (2 pages × 3 charts + macro summary)
# ═══════════════════════════════════════════════════════════════════════════════

def build_pages_inflation(macro: dict) -> list:
    """
    Returns 2 pages, each with 3 inflation charts and a verbal macro summary.

    Page 1: CPI Headline, CPI Core, PCE
    Page 2: Core PCE, PPI (Final Demand), 5Y Breakeven
    """
    inflation = macro.get("inflation", {})

    groups = [
        {
            "series": [
                ("CPI (Headline)",  C["blue"],   2.0, "YoY %"),
                ("CPI (Core)",      C["indigo"], 2.0, "YoY %"),
                ("PCE",             C["teal"],   2.0, "YoY %"),
            ],
            "desc": (
                "CPI Headline, Core CPI & PCE — year-over-year % change, 10-year history.  "
                "Dashed amber = Fed 2% target.  Shaded pink = macro stress periods.  "
                "Dashed grey = 12-month rolling average."
            ),
        },
        {
            "series": [
                ("Core PCE",        C["green"],  2.0, "YoY %"),
                ("PPI (Final Dem)", C["orange"], None, "YoY %"),
                ("5Y Breakeven",    C["purple"], 2.0,  "Rate %"),
            ],
            "desc": (
                "Core PCE (Fed-preferred), PPI Final Demand & 5-Year Breakeven — pipeline "
                "pressures and market inflation expectations, 10-year history.  "
                "Dashed amber = 2% target.  Shaded pink = stress periods."
            ),
        },
    ]

    pages = []
    for page_idx, grp in enumerate(groups):
        subtitle = f"({page_idx + 1}/2)"
        fig = _new_page("Inflation Indicators", grp["desc"], subtitle=subtitle)

        # Three charts side by side
        chart_w, chart_h = 0.27, 0.44
        chart_y = 0.40
        gap     = 0.035
        x0      = 0.05

        series_data = []
        for ci, (key, col, ref, ylabel) in enumerate(grp["series"]):
            x  = x0 + ci * (chart_w + gap)
            ax = fig.add_axes([x, chart_y, chart_w, chart_h])
            s  = inflation.get(key)
            draw_macro_chart(ax, s, title=key, ylabel=ylabel, ref_line=ref, color=col)
            series_data.append((key, s))

        # Macro summary panel
        bullets, commentary = _generate_macro_bullets(series_data, "inflation")
        _draw_macro_summary_panel(
            fig, bullets, commentary,
            section_title="Inflation",
            rect=[0.05, 0.055, 0.90, 0.305],
        )

        pages.append(fig)

    return pages


# ═══════════════════════════════════════════════════════════════════════════════
# Labor Market pages (2 pages × 3 charts + macro summary)
# ═══════════════════════════════════════════════════════════════════════════════

def build_pages_labor(macro: dict) -> list:
    """
    Returns 2 pages, each with 3 labor-market charts and a verbal macro summary.

    Page 1: Unemployment Rate, Nonfarm Payrolls, Job Openings
    Page 2: Initial Claims, LFPR, Avg Hourly Earnings
    """
    labor = macro.get("labor", {})

    groups = [
        {
            "series": [
                ("Unemployment Rate", C["red"],  None, "Rate %"),
                ("Nonfarm Payrolls",  C["blue"], None, "MoM Chg (000s)"),
                ("Job Openings",      C["teal"], None, "000s"),
            ],
            "desc": (
                "Unemployment Rate, Nonfarm Payrolls & JOLTS Job Openings — demand-side "
                "labor indicators, 10-year history.  Shaded regions = key macro stress events."
            ),
        },
        {
            "series": [
                ("Initial Claims",      C["orange"], None, "000s"),
                ("LFPR",                C["purple"], None, "Rate %"),
                ("Avg Hourly Earnings", C["indigo"], None, "YoY %"),
            ],
            "desc": (
                "Initial Jobless Claims, Labor Force Participation & Avg Hourly Earnings — "
                "supply-side and wage indicators, 10-year history.  "
                "Shaded regions = key macro stress events."
            ),
        },
    ]

    pages = []
    for page_idx, grp in enumerate(groups):
        subtitle = f"({page_idx + 1}/2)"
        fig = _new_page("Labor Market Indicators", grp["desc"], subtitle=subtitle)

        chart_w, chart_h = 0.27, 0.44
        chart_y = 0.40
        gap     = 0.035
        x0      = 0.05

        series_data = []
        for ci, (key, col, ref, ylabel) in enumerate(grp["series"]):
            x  = x0 + ci * (chart_w + gap)
            ax = fig.add_axes([x, chart_y, chart_w, chart_h])
            s  = labor.get(key)
            draw_macro_chart(ax, s, title=key, ylabel=ylabel, ref_line=ref, color=col)
            series_data.append((key, s))

        bullets, commentary = _generate_macro_bullets(series_data, "labor")
        _draw_macro_summary_panel(
            fig, bullets, commentary,
            section_title="Labor Market",
            rect=[0.05, 0.055, 0.90, 0.305],
        )

        pages.append(fig)

    return pages


# ── Backwards-compatible single-page wrappers ──────────────────────────────────

def build_page_inflation(macro: dict) -> plt.Figure:
    """Return just the first inflation page (legacy compatibility)."""
    return build_pages_inflation(macro)[0]


def build_page_labor(macro: dict) -> plt.Figure:
    """Return just the first labor page (legacy compatibility)."""
    return build_pages_labor(macro)[0]


# ═══════════════════════════════════════════════════════════════════════════════
# PDF assembler
# ═══════════════════════════════════════════════════════════════════════════════

def assemble_report(pages: list) -> str:
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_PDF)
    with PdfPages(output_path) as pdf:
        for fig in pages:
            pdf.savefig(fig, bbox_inches="tight", dpi=PAGE_DPI)
            plt.close(fig)
    print(f"\n  PDF saved → {output_path}")
    return output_path
