"""
main.py
-------
Entry point for the Financial Markets Report generator.

Run with:
    python main.py

Produces:  financial_report_feb2026.pdf  in the project root.

Page structure:
  1   – Market Overview
  2   – Equity Sector Analysis  (bar chart + summary table with analyst views)
  3–8 – Sector ETF 10Y History Charts  (2 per page, 6 pages)
  9   – Inflation Indicators  (10Y, annotated)
  10  – Labor Market  (10Y, annotated)
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
    build_page_market_overview,
    build_page_sector_analysis,
    build_pages_sector_history,
    build_page_inflation,
    build_page_labor,
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

    print("  • Page 1  – Market Overview")
    pages.append(build_page_market_overview(indices))

    print("  • Page 2  – Sector Analysis (table + analyst views)")
    pages.append(build_page_sector_analysis(sectors))

    print("  • Pages 3–8  – Sector ETF 10Y History Charts (2/page)")
    sector_pages = build_pages_sector_history(sectors)
    pages.extend(sector_pages)
    print(f"      → {len(sector_pages)} pages generated")

    page_num = 2 + len(sector_pages) + 1
    print(f"  • Page {page_num}  – Inflation Indicators (10Y)")
    pages.append(build_page_inflation(macro))

    print(f"  • Page {page_num + 1}  – Labor Market (10Y)")
    pages.append(build_page_labor(macro))

    print(f"\n  Total pages: {len(pages)}")

    # ── 3. Save PDF ────────────────────────────────────────────────────────
    pdf_path = assemble_report(pages)

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
        import matplotlib.pyplot as plt
        from financial_report.config import OUTPUT_DIR, OUTPUT_PDF as _OUTPUT_PDF

        builders_args = [
            ("page1",  build_page_market_overview,  [indices]),
            ("page2",  build_page_sector_analysis,  [sectors]),
        ]
        for p_idx, sector_fig in enumerate(build_pages_sector_history(sectors), start=3):
            builders_args.append((f"page{p_idx}", lambda *a, fig=sector_fig: fig, []))
        builders_args.append((f"page{len(builders_args)+1}", build_page_inflation, [macro]))
        builders_args.append((f"page{len(builders_args)+1}", build_page_labor,     [macro]))

        for page_id, builder, args in builders_args:
            fig = builder(*args)
            out = os.path.join(OUTPUT_DIR, _OUTPUT_PDF.replace(".pdf", f"_{page_id}.png"))
            fig.savefig(out, dpi=120, bbox_inches="tight")
            plt.close(fig)
            print(f"    → {out}")

    print("\n  Done!  Report ready at:", pdf_path)
    return pdf_path


if __name__ == "__main__":
    main()
