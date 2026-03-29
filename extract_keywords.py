"""
Keyword Research Extractor
--------------------------
Reads an analysis JSON file and outputs a plain-text file containing only:
  - Gig title
  - Gig description
  - Tags / keywords

Designed to produce a compact file that an LLM can process directly.

Usage:
  python extract_keywords.py <analysis_json_file>
  python extract_keywords.py "keyword_analysis/custom website development_analysis.json"
  python extract_keywords.py "keyword_analysis/custom website development_analysis.json" --output my_keywords.txt
"""

import json
import sys
import os
import argparse
from pathlib import Path


def extract_keywords(input_file, output_file=None):
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

    # Default output filename next to the input file
    if not output_file:
        output_file = input_path.parent / f"{input_path.stem}_keywords.txt"

    lines = []

    lines.append(f"KEYWORD RESEARCH — {keyword}")
    lines.append(f"Total gigs: {total}")
    lines.append("=" * 80)
    lines.append("")

    for idx, gig in enumerate(gigs, 1):
        title       = gig.get('gig', {}).get('title', '').strip()
        description = gig.get('description', {}).get('description', '').strip()
        tags        = gig.get('tags', [])

        lines.append(f"GIG {idx} of {total}")
        lines.append("-" * 60)

        lines.append(f"TITLE:\n{title}")
        lines.append("")

        lines.append("DESCRIPTION:")
        lines.append(description if description else "(no description)")
        lines.append("")

        lines.append("TAGS / KEYWORDS:")
        if tags:
            for tag in tags:
                lines.append(f"  - {tag}")
        else:
            lines.append("  (none)")

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
        description='Extract titles, descriptions, and tags from an analysis JSON for keyword research',
        epilog='Example: python extract_keywords.py "keyword_analysis/custom website development_analysis.json"'
    )
    parser.add_argument('input', help='Path to the analysis JSON file')
    parser.add_argument('--output', '-o', help='Output .txt file path (optional)')
    args = parser.parse_args()

    extract_keywords(args.input, args.output)


if __name__ == '__main__':
    main()
