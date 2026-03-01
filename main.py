"""
main.py
-------
Entry point for the Financial Markets Report generator.

Run with:
    python main.py

Produces:  financial_report_feb2026.pdf  in the project root.

Data sources (in priority order):
  1. Live data  – yfinance (prices/fundamentals) + FRED CSV (macro)
  2. Simulation – deterministic synthetic data if network is unavailable

Page structure:
  1    – Market Commentary   (executive summary)
  2    – Market Overview     (2-row detailed mini-charts)
  3    – Sector Analysis     (table + bar chart + analyst views)
  4–14 – Sector ETF 10Y History Charts  (1 per page, top/bottom-5 performers)
  15–16 – Inflation Indicators  (3 charts + macro summary per page)
  17–18 – Labor Market           (3 charts + macro summary per page)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from financial_report.data_fetcher import (
    fetch_market_overview  as _live_indices,
    fetch_sector_data      as _live_sectors,
    fetch_macro_data       as _live_macro,
)
from financial_report.data_simulator import (
    simulate_market_overview as _sim_indices,
    simulate_sector_data     as _sim_sectors,
    simulate_macro_data      as _sim_macro,
)
from financial_report.pdf_builder import (
    build_page_market_commentary,
    build_page_market_overview,
    build_page_sector_analysis,
    build_pages_sector_history,
    build_pages_inflation,
    build_pages_labor,
    assemble_report,
)


def _fetch_with_fallback(live_fn, sim_fn, label: str):
    """
    Try the live data function first.
    If it raises or returns empty/all-None results, fall back to the simulator
    and clearly log which path was taken.
    Returns (data, is_live: bool).
    """
    try:
        result = live_fn()
        # Indices / sectors list: must have at least 1 row with a real price
        if isinstance(result, list):
            if len(result) == 0:
                raise ValueError("live fetch returned empty list")
            import numpy as np, pandas as pd
            live_rows = sum(
                1 for r in result
                if pd.notna(r.get("current", np.nan)) or
                   pd.notna(r.get("return_ytd", np.nan))
            )
            if live_rows == 0:
                raise ValueError("live fetch returned all-NaN results")
        # Macro dict: at least one series must be a non-None pd.Series with data
        if isinstance(result, dict):
            import pandas as pd
            any_live = any(
                isinstance(v, pd.Series) and len(v) > 0
                for section in result.values()
                for v in (section.values() if isinstance(section, dict) else [section])
            )
            if not any_live:
                raise ValueError("all live macro series are empty/None")
        return result, True
    except Exception as exc:
        print(f"  [fallback] {label} live fetch failed ({exc}); using simulated data")
        return sim_fn(), False


def main():
    print("=" * 60)
    print("  Financial Markets Report  –  Feb 2026")
    print("=" * 60)

    # ── 1. Data acquisition ────────────────────────────────────────────────
    print("\n[1/3] Fetching market indices …")
    indices, indices_live = _fetch_with_fallback(
        _live_indices, _sim_indices, "market indices")
    print(f"      → {len(indices)} indices  "
          f"({'live' if indices_live else 'SIMULATED – no network access'})")

    print("\n[2/3] Fetching sector data …")
    sectors, sectors_live = _fetch_with_fallback(
        _live_sectors, _sim_sectors, "sector data")
    print(f"      → {len(sectors)} sectors  "
          f"({'live' if sectors_live else 'SIMULATED – no network access'})")

    print("\n[3/3] Fetching macro data …")
    macro, macro_live = _fetch_with_fallback(
        _live_macro, _sim_macro, "macro data")
    infl_count  = sum(1 for v in macro["inflation"].values() if v is not None)
    labor_count = sum(1 for v in macro["labor"].values()     if v is not None)
    print(f"      → {infl_count} inflation series, {labor_count} labor series  "
          f"({'live' if macro_live else 'SIMULATED – no network access'})")

    data_is_live = indices_live and sectors_live and macro_live
    if not data_is_live:
        print("\n  *** NOTE: One or more data sources unavailable (network blocked). ***")
        print("  *** Charts show statistically-realistic simulated data.           ***")
        print("  *** Run on a machine with internet access for live market data.   ***")

    # ── 2. Page composition ────────────────────────────────────────────────
    print("\n  Building PDF pages …")
    pages = []

    print("  • Page 1  – Market Commentary (executive summary)")
    pages.append(build_page_market_commentary(indices, sectors, macro,
                                              data_is_live=data_is_live))

    print("  • Page 2  – Market Overview (detailed 2-row mini-charts)")
    pages.append(build_page_market_overview(indices))

    print("  • Page 3  – Sector Analysis (table + analyst views)")
    pages.append(build_page_sector_analysis(sectors))

    print(f"  • Pages 4–{3 + len(sectors)}  – Sector ETF 10Y History Charts (1/page, top/bottom-5 table)")
    sector_pages = build_pages_sector_history(sectors)
    pages.extend(sector_pages)
    print(f"      → {len(sector_pages)} pages generated")

    infl_start = 3 + len(sector_pages) + 1
    print(f"  • Pages {infl_start}–{infl_start + 1}  – Inflation Indicators (3 charts + summary per page)")
    infl_pages = build_pages_inflation(macro)
    pages.extend(infl_pages)
    print(f"      → {len(infl_pages)} pages generated")

    labor_start = infl_start + len(infl_pages)
    print(f"  • Pages {labor_start}–{labor_start + 1}  – Labor Market (3 charts + summary per page)")
    labor_pages = build_pages_labor(macro)
    pages.extend(labor_pages)
    print(f"      → {len(labor_pages)} pages generated")

    print(f"\n  Total pages: {len(pages)}")

    # ── 3. Save PDF (keep figures open so fallback PNG export can use them) ──
    pdf_path = assemble_report(pages, close_figures=False)

    # ── 4. Export PNG previews ─────────────────────────────────────────────
    print("\n  Exporting page previews as PNG …")
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=120)
        for i, img in enumerate(images, start=1):
            png_path = pdf_path.replace(".pdf", f"_page{i}.png")
            img.save(png_path, "PNG")
            print(f"    → {png_path}")
    except ImportError:
        # pdf2image not available – save directly from the still-open figures.
        import matplotlib.pyplot as plt
        from financial_report.config import OUTPUT_DIR, OUTPUT_PDF as _OUTPUT_PDF

        for i, fig in enumerate(pages, start=1):
            out = os.path.join(OUTPUT_DIR,
                               _OUTPUT_PDF.replace(".pdf", f"_page{i}.png"))
            fig.savefig(out, dpi=120, bbox_inches="tight")
            print(f"    → {out}")

    # ── 5. Close figures ───────────────────────────────────────────────────
    import matplotlib.pyplot as plt
    for fig in pages:
        plt.close(fig)

    print("\n  Done!  Report ready at:", pdf_path)
    return pdf_path


if __name__ == "__main__":
    main()
