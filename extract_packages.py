"""
Package Data Extractor
-----------------------
Reads an analysis JSON file and outputs a plain-text file containing only
package information for every gig:
  - Tier (Basic / Standard / Premium)
  - Package title and description
  - Price and delivery time
  - Features / what's included

Designed to produce a compact file that an LLM can process directly.

Usage:
  python extract_packages.py <analysis_json_file>
  python extract_packages.py "keyword_analysis/custom website development_analysis.json"
  python extract_packages.py "keyword_analysis/custom website development_analysis.json" --output my_packages.txt
"""

import json
import sys
import argparse
from pathlib import Path


def format_features(features):
    """Turn the features dict into readable lines."""
    lines = []
    for name, value in features.items():
        if value is True:
            lines.append(f"    + {name}")
        elif value is False:
            pass  # skip things not included
        else:
            lines.append(f"    + {name}: {value}")
    return lines


def extract_packages(input_file, output_file=None):
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"[ERROR] File not found: {input_file}")
        sys.exit(1)

    with open(input_path, encoding='utf-8') as f:
        data = json.load(f)

    gigs = data.get('gigs', [])
    keyword = data.get('keyword', input_path.stem)
    total = len(gigs)

    if not gigs:
        print("[ERROR] No gigs found in this analysis file.")
        sys.exit(1)

    if not output_file:
        output_file = input_path.parent / f"{input_path.stem}_packages.txt"

    lines = []

    lines.append(f"PACKAGE RESEARCH — {keyword}")
    lines.append(f"Total gigs: {total}")
    lines.append("=" * 80)
    lines.append("")

    for idx, gig in enumerate(gigs, 1):
        title    = gig.get('gig', {}).get('title', '').strip()
        seller   = gig.get('seller', {}).get('username', 'unknown')
        packages = gig.get('packages', [])

        lines.append(f"GIG {idx} of {total}  |  Seller: {seller}")
        lines.append(f"Title: {title}")
        lines.append("-" * 60)

        if not packages:
            lines.append("  (no package data)")
        else:
            for pkg in packages:
                tier         = pkg.get('tier', 'Package')
                pkg_title    = pkg.get('title', '').strip()
                pkg_desc     = pkg.get('description', '').strip()
                price        = pkg.get('price', 0)
                delivery     = pkg.get('delivery_time_days', 0)
                revisions    = pkg.get('revisions', 0)
                unlimited_rev = pkg.get('revisions_unlimited', False)
                features     = pkg.get('features', {})

                rev_text = "Unlimited" if unlimited_rev else str(int(revisions))

                lines.append(f"  [{tier.upper()}] {pkg_title}")
                lines.append(f"  Price: ${price:,.0f}  |  Delivery: {int(delivery)} day(s)  |  Revisions: {rev_text}")
                lines.append(f"  Description: {pkg_desc if pkg_desc else '(none)'}")

                if features:
                    lines.append("  Includes:")
                    lines.extend(format_features(features))

                lines.append("")

        lines.append("=" * 80)
        lines.append("")

    output = "\n".join(lines)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)

    size_kb = Path(output_file).stat().st_size / 1024
    print(f"Done -- {total} gigs written to: {output_file}  ({size_kb:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(
        description='Extract package data from an analysis JSON for pricing research',
        epilog='Example: python extract_packages.py "keyword_analysis/custom website development_analysis.json"'
    )
    parser.add_argument('input', help='Path to the analysis JSON file')
    parser.add_argument('--output', '-o', help='Output .txt file path (optional)')
    args = parser.parse_args()

    extract_packages(args.input, args.output)


if __name__ == '__main__':
    main()
