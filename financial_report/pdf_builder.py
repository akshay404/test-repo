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

# ── Global matplotlib style (dark theme) ───────────────────────────────────────
plt.rcParams.update({
    "font.family":        "DejaVu Sans",
    "font.size":          8,
    "figure.facecolor":   C["bg"],
    "axes.facecolor":     C["surface"],
    "axes.edgecolor":     C["divider"],
    "text.color":         C["text"],
    "axes.labelcolor":    C["text2"],
    "xtick.color":        C["text2"],
    "ytick.color":        C["text2"],
    "grid.color":         C["grid"],
    "legend.facecolor":   C["surface"],
    "legend.edgecolor":   C["divider"],
    "legend.labelcolor":  C["text"],
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
    ax_ftr.set_facecolor(C["primary"])
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
# Page 1 – Market Commentary  (executive summary / intro)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_commentary_content(indices: list, sectors: list, macro: dict) -> dict:
    """
    Derive all data-driven narrative fragments from simulated data
    so the commentary stays internally consistent with the report numbers.
    """
    # ── Index snapshot ──────────────────────────────────────────────────────
    eq   = [r for r in indices if r["category"] == "Equity"]
    fi   = [r for r in indices if r["category"] == "Fixed Income"]
    cmdty= [r for r in indices if r["category"] == "Commodities"]

    def _avg_ytd(rows):
        vals = [r["return_ytd"] for r in rows if r.get("return_ytd") is not None
                and not pd.isna(r["return_ytd"])]
        return sum(vals) / len(vals) if vals else 0.0

    eq_avg   = _avg_ytd(eq)
    fi_avg   = _avg_ytd(fi)
    cmdty_avg= _avg_ytd(cmdty)

    best_idx  = max(indices, key=lambda r: r.get("return_ytd") or -999)
    worst_idx = min(indices, key=lambda r: r.get("return_ytd") or 999)
    best_sec  = max(sectors,  key=lambda s: s.get("return_ytd") or -999)
    worst_sec = min(sectors,  key=lambda s: s.get("return_ytd") or 999)

    sp500 = next((r for r in indices if "S&P" in r["name"]), None)
    sp_ytd = sp500["return_ytd"] if sp500 else 0.0
    sp_cur = sp500["current"]    if sp500 else 0.0

    nasdaq = next((r for r in indices if "NASDAQ" in r["name"]), None)
    nasdaq_ytd = nasdaq["return_ytd"] if nasdaq else 0.0

    gold  = next((r for r in indices if "Gold"    in r["name"]), None)
    crude = next((r for r in indices if "WTI"     in r["name"]), None)
    tlt   = next((r for r in indices if "20Y"     in r["name"]), None)
    hy    = next((r for r in indices if "High Yield" in r["name"]), None)

    # ── Macro snapshot ──────────────────────────────────────────────────────
    infl    = macro.get("inflation", {})
    labor   = macro.get("labor", {})
    cpi_s   = infl.get("CPI (Headline)")
    cpi_val = float(cpi_s.dropna().iloc[-1]) if cpi_s is not None else 3.2
    pce_s   = infl.get("Core PCE")
    pce_val = float(pce_s.dropna().iloc[-1]) if pce_s is not None else 2.8
    un_s    = labor.get("Unemployment Rate")
    un_val  = float(un_s.dropna().iloc[-1]) if un_s is not None else 4.1
    nfp_s   = labor.get("Nonfarm Payrolls")
    nfp_val = float(nfp_s.dropna().iloc[-1]) if nfp_s is not None else 150.0

    # ── Regime description ──────────────────────────────────────────────────
    if eq_avg > 8:
        regime = "Risk-on"
        regime_desc = "broad-based equity strength"
    elif eq_avg > 2:
        regime = "Cautiously constructive"
        regime_desc = "selective equity gains amid mixed macro signals"
    elif eq_avg > -2:
        regime = "Range-bound"
        regime_desc = "indecisive price action across asset classes"
    else:
        regime = "Risk-off"
        regime_desc = "broad equity weakness and flight to quality"

    # ── Fed stance ──────────────────────────────────────────────────────────
    if cpi_val > 4.0:
        fed_stance = "restrictive — with further tightening not ruled out"
        fed_short  = "Rates: Restrictive"
    elif cpi_val > 2.5:
        fed_stance = "on hold, balancing disinflation progress against labour resilience"
        fed_short  = "Rates: On Hold"
    else:
        fed_stance = "pivoting toward easing, with markets pricing 2–3 cuts in 2026"
        fed_short  = "Rates: Easing Bias"

    return dict(
        eq_avg=eq_avg, fi_avg=fi_avg, cmdty_avg=cmdty_avg,
        best_idx=best_idx, worst_idx=worst_idx,
        best_sec=best_sec, worst_sec=worst_sec,
        sp_ytd=sp_ytd, sp_cur=sp_cur,
        nasdaq_ytd=nasdaq_ytd,
        gold=gold, crude=crude, tlt=tlt, hy=hy,
        cpi_val=cpi_val, pce_val=pce_val,
        un_val=un_val, nfp_val=nfp_val,
        regime=regime, regime_desc=regime_desc,
        fed_stance=fed_stance, fed_short=fed_short,
    )


def build_page_market_commentary(indices: list, sectors: list,
                                 macro: dict) -> plt.Figure:
    """
    Page 1 – Executive market commentary.

    Left column  (65 %): narrative paragraphs covering equities, fixed income,
                         commodities, and macro backdrop.
    Right column (30 %): key stats boxes + themes + risk watchlist.
    """
    desc = (
        "Monthly executive summary covering global market conditions, sector themes, "
        "macro backdrop, and key risks as of the report date.  All figures are simulated."
    )
    fig = _new_page("Market Commentary", desc)
    d   = _build_commentary_content(indices, sectors, macro)

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _panel(rect, fc=C["surface"], border_color=None):
        ax = fig.add_axes(rect)
        ax.set_facecolor(fc)
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        if border_color:
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_color(border_color)
                spine.set_linewidth(0.5)
        return ax

    def _heading(ax, y, text, size=9, color=C["primary_light"]):
        ax.text(0.0, y, text, fontsize=size, fontweight="bold",
                color=color, va="top", ha="left", transform=ax.transAxes)

    def _body(ax, y, text, size=7.2, color=C["text"], max_chars=82):
        wrapped = _wrap_text(text, max_chars)
        ax.text(0.0, y, wrapped, fontsize=size, color=color,
                va="top", ha="left", transform=ax.transAxes,
                linespacing=1.5, clip_on=True)

    # ── Left narrative column ────────────────────────────────────────────────
    ax_l = _panel([0.03, 0.065, 0.61, 0.79])

    # ── Section: Executive Summary ──
    _heading(ax_l, 0.985, "Executive Summary")
    exec_text = (
        f"Global financial markets closed February 2026 in a {d['regime'].lower()} posture, "
        f"characterised by {d['regime_desc']}. "
        f"The S&P 500 {'gained' if d['sp_ytd'] >= 0 else 'fell'} {abs(d['sp_ytd']):.1f}% "
        f"year-to-date, with large-cap technology continuing to lead on the back of AI-related "
        f"earnings momentum. The NASDAQ 100 {'advanced' if d['nasdaq_ytd'] >= 0 else 'declined'} "
        f"{abs(d['nasdaq_ytd']):.1f}% YTD, while broader indices reflected more mixed returns "
        f"as rate-sensitive sectors lagged. Cross-asset, equities "
        f"averaged {d['eq_avg']:+.1f}% YTD, fixed income {d['fi_avg']:+.1f}%, "
        f"and commodities {d['cmdty_avg']:+.1f}%."
    )
    _body(ax_l, 0.942, exec_text)

    # ── Section: Equity Markets ──
    _heading(ax_l, 0.790, "Equity Markets")
    eq_text = (
        f"The best-performing benchmark in the period was {d['best_idx']['name']} "
        f"({d['best_idx']['return_ytd']:+.1f}% YTD), driven by strong earnings revisions "
        f"and favourable sector composition. At the sector level, "
        f"{d['best_sec']['sector']} ({d['best_sec']['return_ytd']:+.1f}% YTD) led the market, "
        f"while {d['worst_sec']['sector']} ({d['worst_sec']['return_ytd']:+.1f}% YTD) lagged "
        f"amid headwinds from {'rising rates and regulatory uncertainty' if 'Utilit' in d['worst_sec']['sector'] or 'Real' in d['worst_sec']['sector'] else 'earnings misses and softening demand'}. "
        f"Emerging markets remained under pressure ({d['worst_idx']['name']} "
        f"{d['worst_idx']['return_ytd']:+.1f}% YTD), with dollar strength and geopolitical "
        f"uncertainty weighing on sentiment."
    )
    _body(ax_l, 0.748, eq_text)

    # ── Section: Fixed Income & Rates ──
    _heading(ax_l, 0.597, "Fixed Income & Rates")
    tlt_ytd  = d["tlt"]["return_ytd"]  if d["tlt"]  else -4.0
    hy_ytd   = d["hy"]["return_ytd"]   if d["hy"]   else +3.5
    fi_text = (
        f"The Federal Reserve held policy {'steady' if 'hold' in d['fed_stance'].lower() else 'at current levels'}, "
        f"keeping the Fed Funds target range unchanged while reiterating data-dependency. "
        f"Long-duration Treasuries {'rallied' if tlt_ytd >= 0 else 'sold off'} "
        f"({abs(tlt_ytd):.1f}% YTD), as markets debated the trajectory of terminal rates. "
        f"Credit spreads remained {'broadly contained' if hy_ytd >= 0 else 'under modest pressure'}, "
        f"with high-yield {'+' if hy_ytd >= 0 else ''}{hy_ytd:.1f}% YTD. "
        f"The investment-grade corporate market held up relatively well, underpinned by "
        f"solid balance sheets and limited near-term refinancing risk. "
        f"The Fed is currently {d['fed_stance']}."
    )
    _body(ax_l, 0.556, fi_text)

    # ── Section: Commodities ──
    _heading(ax_l, 0.418, "Commodities")
    gold_ytd  = d["gold"]["return_ytd"]  if d["gold"]  else +8.0
    crude_ytd = d["crude"]["return_ytd"] if d["crude"] else -5.0
    cmdty_text = (
        f"Gold {'extended its rally' if gold_ytd > 5 else 'moved modestly higher' if gold_ytd > 0 else 'retreated'} "
        f"({gold_ytd:+.1f}% YTD), supported by central bank demand and geopolitical hedging. "
        f"WTI crude oil {'gained' if crude_ytd >= 0 else 'declined'} {abs(crude_ytd):.1f}% YTD, "
        f"reflecting {'supply discipline from OPEC+ and firm demand' if crude_ytd >= 0 else 'demand uncertainty and rising non-OPEC supply offsetting OPEC+ cuts'}. "
        f"Industrial metals were mixed: copper benefited from China stimulus hopes, "
        f"while natural gas remained volatile given storage dynamics and weather effects."
    )
    _body(ax_l, 0.376, cmdty_text)

    # ── Section: Macro Backdrop ──
    _heading(ax_l, 0.245, "Macro Backdrop")
    macro_text = (
        f"The US economy continued its resilient expansion heading into February 2026. "
        f"Headline CPI stood at {d['cpi_val']:.1f}% YoY, with Core PCE at {d['pce_val']:.1f}% — "
        f"{'still above' if d['pce_val'] > 2.0 else 'near'} the Fed's 2% target. "
        f"The labour market remained {'tight' if d['un_val'] < 4.2 else 'resilient'}, "
        f"with unemployment at {d['un_val']:.1f}% and nonfarm payrolls printing "
        f"{d['nfp_val']:+.0f}K in the latest month. "
        f"Consumer spending has been supported by real wage growth, though some moderation "
        f"is expected as excess savings are depleted. Global growth diverged: the Eurozone "
        f"showed tentative stabilisation while China's recovery remained uneven."
    )
    _body(ax_l, 0.203, macro_text)

    # ── Right column: stats + themes ────────────────────────────────────────
    rx = 0.66   # right column left edge
    rw = 0.31   # right column width

    # ── Market Regime box ──
    ax_reg = _panel([rx, 0.755, rw, 0.105], fc=C["primary_bg"])
    ax_reg.add_patch(mpatches.Rectangle(
        (0, 0), 0.006, 1.0, facecolor=C["accent"],
        transform=ax_reg.transAxes, clip_on=True, zorder=3))
    ax_reg.text(0.018, 0.88, "MARKET REGIME", fontsize=6.5, fontweight="bold",
                color=C["primary_dark"], va="top", transform=ax_reg.transAxes)
    ax_reg.text(0.018, 0.62, d["regime"],
                fontsize=11, fontweight="bold", color=C["accent"],
                va="top", transform=ax_reg.transAxes)
    ax_reg.text(0.018, 0.24, d["fed_short"],
                fontsize=7.5, color=C["text2"], va="top", transform=ax_reg.transAxes)

    # ── Key Stats box ──
    ax_stats = _panel([rx, 0.565, rw, 0.175], fc=C["surface"])
    ax_stats.add_patch(mpatches.Rectangle(
        (0, 0.92), 1.0, 0.08, facecolor=C["primary"],
        transform=ax_stats.transAxes, clip_on=True, zorder=2))
    ax_stats.text(0.5, 0.96, "KEY STATS — FEB 2026", fontsize=6.5,
                  fontweight="bold", color="white", ha="center", va="center",
                  transform=ax_stats.transAxes)

    stats = [
        ("S&P 500 YTD",    f"{d['sp_ytd']:+.1f}%",   _val_color(d["sp_ytd"])),
        ("NASDAQ 100 YTD", f"{d['nasdaq_ytd']:+.1f}%", _val_color(d["nasdaq_ytd"])),
        ("Top Sector",     d["best_sec"]["sector"][:16], C["pos_light"]),
        ("CPI (Headline)", f"{d['cpi_val']:.1f}% YoY",
         C["neg_light"] if d["cpi_val"] > 3 else C["pos_light"]),
        ("Unemployment",   f"{d['un_val']:.1f}%",
         C["pos_light"] if d["un_val"] < 4.5 else C["neg_light"]),
        ("NFP (Latest)",   f"{d['nfp_val']:+.0f}K",   _val_color(d["nfp_val"])),
    ]
    row_h_s = 0.88 / len(stats)
    for i, (label, val, vc) in enumerate(stats):
        y  = 0.88 - i * row_h_s
        bg = C["bg"] if i % 2 == 0 else C["surface"]
        ax_stats.add_patch(mpatches.Rectangle(
            (0, y - row_h_s), 1.0, row_h_s, facecolor=bg,
            transform=ax_stats.transAxes, clip_on=True, zorder=1))
        ax_stats.text(0.04, y - row_h_s / 2, label, fontsize=6.5,
                      color=C["text2"], va="center", transform=ax_stats.transAxes)
        ax_stats.text(0.96, y - row_h_s / 2, val,   fontsize=6.8,
                      color=vc, va="center", ha="right", fontweight="bold",
                      transform=ax_stats.transAxes)

    # ── Key Themes box ──
    ax_th = _panel([rx, 0.37, rw, 0.180], fc=C["surface"])
    ax_th.add_patch(mpatches.Rectangle(
        (0, 0.91), 1.0, 0.09, facecolor=C["primary"],
        transform=ax_th.transAxes, clip_on=True, zorder=2))
    ax_th.text(0.5, 0.955, "KEY THEMES", fontsize=6.5, fontweight="bold",
               color="white", ha="center", va="center", transform=ax_th.transAxes)
    themes = [
        "AI capital expenditure cycle driving tech outperformance",
        "Disinflation progress — Fed rate-cut trajectory in focus",
        "US exceptionalism vs. slowing global growth divergence",
        "Geopolitical risk premium embedded in energy & gold",
        "Credit resilience underpins risk appetite",
    ]
    t_h = 0.88 / len(themes)
    for i, theme in enumerate(themes):
        y_t = 0.88 - i * t_h
        ax_th.add_patch(mpatches.Rectangle(
            (0, y_t - t_h), 1.0, t_h, facecolor=C["bg"] if i % 2 == 0 else C["surface"],
            transform=ax_th.transAxes, clip_on=True, zorder=1))
        ax_th.text(0.04, y_t - t_h / 2, f"• {theme}", fontsize=6.2,
                   color=C["text"], va="center", transform=ax_th.transAxes,
                   clip_on=True)

    # ── Risks to Watch box ──
    ax_risk = _panel([rx, 0.190, rw, 0.165], fc=C["surface"])
    ax_risk.add_patch(mpatches.Rectangle(
        (0, 0.91), 1.0, 0.09, facecolor=C["neg"],
        transform=ax_risk.transAxes, clip_on=True, zorder=2))
    ax_risk.text(0.5, 0.955, "RISKS TO WATCH", fontsize=6.5, fontweight="bold",
                 color="white", ha="center", va="center", transform=ax_risk.transAxes)
    risks = [
        "Re-acceleration of inflation derailing rate-cut path",
        "Labour market softening faster than expected",
        "Geopolitical escalation disrupting energy supply",
        "China property sector tail-risk re-emerging",
    ]
    r_h = 0.88 / len(risks)
    for i, risk in enumerate(risks):
        y_r = 0.88 - i * r_h
        ax_risk.add_patch(mpatches.Rectangle(
            (0, y_r - r_h), 1.0, r_h, facecolor=C["neg_bg"] if i % 2 == 0 else C["surface"],
            transform=ax_risk.transAxes, clip_on=True, zorder=1))
        ax_risk.text(0.04, y_r - r_h / 2, f"⚠  {risk}", fontsize=6.0,
                     color=C["neg_light"], va="center", transform=ax_risk.transAxes,
                     clip_on=True)

    # ── Outlook one-liner at bottom ──
    ax_out = _panel([rx, 0.065, rw, 0.110], fc=C["primary_bg"])
    ax_out.add_patch(mpatches.Rectangle(
        (0, 0), 0.006, 1.0, facecolor=C["primary_light"],
        transform=ax_out.transAxes, clip_on=True, zorder=3))
    ax_out.text(0.018, 0.90, "OUTLOOK", fontsize=6.5, fontweight="bold",
                color=C["primary_dark"], va="top", transform=ax_out.transAxes)
    if d["eq_avg"] > 5:
        outlook_txt = (
            "Constructive on equities near term, with AI-driven earnings upside "
            "offsetting valuation concerns. Maintain duration underweight; "
            "favour quality credit over IG rates."
        )
    elif d["eq_avg"] > 0:
        outlook_txt = (
            "Modestly positive risk posture. Selective equity exposure favoured; "
            "monitor inflation prints closely for Fed pivot catalysts. "
            "Overweight gold and short duration."
        )
    else:
        outlook_txt = (
            "Defensive posture warranted. Reduce risk exposure, overweight "
            "high-quality bonds and gold. Watch for stabilisation signals "
            "before adding cyclical risk."
        )
    ax_out.text(0.018, 0.65, _wrap_text(outlook_txt, 44),
                fontsize=6.2, color=C["text"], va="top",
                transform=ax_out.transAxes, linespacing=1.4, clip_on=True)

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Page 2 – Market Overview
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

def assemble_report(pages: list, close_figures: bool = True) -> str:
    """Save all pages to a PDF.  Set close_figures=False to keep figures open
    so the caller can export PNGs before closing them."""
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_PDF)
    with PdfPages(output_path) as pdf:
        for fig in pages:
            pdf.savefig(fig, bbox_inches="tight", dpi=PAGE_DPI)
            if close_figures:
                plt.close(fig)
    print(f"\n  PDF saved → {output_path}")
    return output_path
