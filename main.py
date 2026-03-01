"""
main.py
-------
Entry point for the Financial Markets Report generator.

Run with:
    python main.py

Produces:  financial_report_feb2026.pdf  in the project root.

Page structure:
  1    – Market Overview  (2-row detailed mini-charts)
  2    – Equity Sector Analysis  (table + bar chart + analyst views)
  3–13 – Sector ETF 10Y History Charts  (1 per page, top/bottom-5 performers)
  14–15 – Inflation Indicators  (3 charts + macro summary per page)
  16–17 – Labor Market           (3 charts + macro summary per page)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from financial_report.data_simulator import (
    simulate_market_overview as fetch_market_overview,
    simulate_sector_data      as fetch_sector_data,
    simulate_macro_data       as fetch_macro_data,
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


def main():
    print("=" * 60)
    print("  Financial Markets Report  –  Feb 2026")
    print("=" * 60)

    # ── 1. Data acquisition ────────────────────────────────────────────────
    print("\n[1/3] Fetching market indices …")
    indices = fetch_market_overview()
    print(f"      → {len(indices)} indices loaded")

    print("\n[2/3] Fetching sector data …")
    sectors = fetch_sector_data()
    print(f"      → {len(sectors)} sectors loaded")

    print("\n[3/3] Fetching macro data …")
    macro = fetch_macro_data()
    infl_count  = sum(1 for v in macro["inflation"].values() if v is not None)
    labor_count = sum(1 for v in macro["labor"].values()     if v is not None)
    print(f"      → {infl_count} inflation series, {labor_count} labor series loaded")

    # ── 2. Page composition ────────────────────────────────────────────────
    print("\n  Building PDF pages …")
    pages = []

    print("  • Page 1  – Market Commentary (executive summary)")
    pages.append(build_page_market_commentary(indices, sectors, macro))

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
