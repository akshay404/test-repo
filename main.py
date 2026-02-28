"""
main.py
-------
Entry point for the Financial Markets Report generator.

Run with:
    python main.py

Produces:  financial_report_feb2026.pdf  in the project root.

Flow:
  1. Fetch all data   (market indices, sectors, VIX, macro)
  2. Build each page  (5 matplotlib figures)
  3. Save to PDF
  4. Convert pages to PNG previews (for display / email attachment)
"""

import sys
import os

# Ensure the repo root is on the path so sub-module imports work
sys.path.insert(0, os.path.dirname(__file__))

from financial_report.data_simulator import (
    simulate_market_overview  as fetch_market_overview,
    simulate_sector_data      as fetch_sector_data,
    simulate_vix_data         as fetch_vix_data,
    simulate_macro_data       as fetch_macro_data,
)
from financial_report.pdf_builder import (
    build_page_market_overview,
    build_page_sector_analysis,
    build_page_vix,
    build_page_inflation,
    build_page_labor,
    assemble_report,
)


def main():
    print("=" * 60)
    print("  Financial Markets Report  –  Feb 2026")
    print("=" * 60)

    # ── 1. Data acquisition ────────────────────────────────────────────────
    print("\n[1/5] Fetching market indices …")
    indices = fetch_market_overview()
    print(f"      → {len(indices)} indices loaded")

    print("\n[2/5] Fetching sector data …")
    sectors = fetch_sector_data()
    print(f"      → {len(sectors)} sectors loaded")

    print("\n[3/5] Fetching VIX …")
    vix = fetch_vix_data()
    print(f"      → VIX current: {vix['current']:.1f}" if vix else "      → VIX unavailable")

    print("\n[4/5] Fetching macro data …")
    macro = fetch_macro_data()
    infl_count  = sum(1 for v in macro["inflation"].values() if v is not None)
    labor_count = sum(1 for v in macro["labor"].values()     if v is not None)
    print(f"      → {infl_count} inflation series, {labor_count} labor series loaded")

    # ── 2. Page composition ────────────────────────────────────────────────
    print("\n[5/5] Building PDF pages …")

    pages = []

    print("  • Page 1 – Market Overview")
    pages.append(build_page_market_overview(indices))

    print("  • Page 2 – Sector Analysis")
    pages.append(build_page_sector_analysis(sectors))

    print("  • Page 3 – VIX / Volatility")
    pages.append(build_page_vix(vix))

    print("  • Page 4 – Inflation Indicators")
    pages.append(build_page_inflation(macro))

    print("  • Page 5 – Labor Market")
    pages.append(build_page_labor(macro))

    # ── 3. Save PDF ────────────────────────────────────────────────────────
    pdf_path = assemble_report(pages)

    # ── 4. Export PNG previews for display ────────────────────────────────
    print("\n  Exporting page previews as PNG …")
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=120)
        for i, img in enumerate(images, start=1):
            png_path = pdf_path.replace(".pdf", f"_page{i}.png")
            img.save(png_path, "PNG")
            print(f"    → {png_path}")
    except ImportError:
        # Fallback: re-render each page figure as PNG (pdf2image not available)
        import matplotlib.pyplot as plt
        from financial_report.config import OUTPUT_DIR, OUTPUT_PDF as _OUTPUT_PDF

        builders = [
            ("page1", build_page_market_overview, [indices]),
            ("page2", build_page_sector_analysis,  [sectors]),
            ("page3", build_page_vix,              [vix]),
            ("page4", build_page_inflation,        [macro]),
            ("page5", build_page_labor,            [macro]),
        ]
        for page_id, builder, args in builders:
            fig = builder(*args)
            out = os.path.join(OUTPUT_DIR, _OUTPUT_PDF.replace(".pdf", f"_{page_id}.png"))
            fig.savefig(out, dpi=120, bbox_inches="tight")
            plt.close(fig)
            print(f"    → {out}")

    print("\n  Done!  Report ready at:", pdf_path)
    return pdf_path


if __name__ == "__main__":
    main()
