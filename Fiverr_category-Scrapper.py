import json
import argparse
import sys
import os
import re
import time
import importlib.util
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from fiverr import session
from fiverr.utils.req import ScraperApiKeyError, ScraperApiQuotaError, ScraperApiError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Import shared functions from the search scraper (filename has a hyphen so
# we use importlib instead of a normal import statement)
# ---------------------------------------------------------------------------
_spec = importlib.util.spec_from_file_location(
    "fiverr_search_scrapper",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Fiverr_search-Scrapper.py")
)
_search_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_search_mod)

sanitize_filename         = _search_mod.sanitize_filename
extract_gig_urls_from_search = _search_mod.extract_gig_urls_from_search
scrape_gig_details        = _search_mod.scrape_gig_details


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def build_page_url(base_url, page):
    """Inject (or replace) the page= param in a category URL."""
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    if page == 1:
        params.pop('page', None)          # page 1 doesn't need the param
    else:
        params['page'] = [str(page)]
    flat = {k: v[0] for k, v in params.items()}
    new_query = urlencode(flat)
    return urlunparse(parsed._replace(query=new_query))


def folder_name_from_url(url):
    """
    Derive a safe output folder name from the category URL path.
    /categories/programming-tech/website-development/custom-websites-development
    -> category_programming-tech_website-development_custom-websites-development
    """
    path = urlparse(url).path
    parts = [p for p in path.split('/') if p and p != 'categories']
    name = 'category_' + '_'.join(parts)
    return sanitize_filename(name)


# ---------------------------------------------------------------------------
# Category page — gig URL extraction
# ---------------------------------------------------------------------------

def extract_gig_urls_from_category(page_data):
    """
    Extract gig info from a Fiverr category page JSON blob.

    Category pages use the same listings[0]['gigs'] path as search pages
    (confirmed by live page inspection), so we delegate to the existing
    search extractor.  The 'has_more' flag is read separately for pagination.
    """
    return extract_gig_urls_from_search(page_data)


def has_more_pages(page_data):
    """Return True if Fiverr says there are more pages after this one."""
    try:
        return bool(page_data['rawListingData']['has_more'])
    except (KeyError, TypeError):
        return False          # when in doubt, stop


# ---------------------------------------------------------------------------
# Main scrape function
# ---------------------------------------------------------------------------

def scrape_category(category_url, api_key=None, output_dir='gigs_data',
                    max_pages=1, delay=2):
    """Scrape gigs from a Fiverr category URL."""

    if not api_key:
        api_key = os.getenv('SCRAPER_API_KEY')

    if not api_key:
        print("❌ No ScraperAPI key found!")
        print("   Option 1: Create .env file with SCRAPER_API_KEY=your_key")
        print("   Option 2: Use --key argument")
        return 0

    session.set_scraper_api_key(api_key)

    folder  = folder_name_from_url(category_url)
    out_dir = Path(output_dir) / folder
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Category URL : {category_url}")
    print(f"📁 Output folder: {out_dir}")
    print(f"📄 Max pages    : {max_pages}")
    print("=" * 60)

    all_gig_infos = []

    # ------------------------------------------------------------------
    # Phase 1 — collect gig listing data across pages
    # ------------------------------------------------------------------
    for page in range(1, max_pages + 1):
        url = build_page_url(category_url, page)
        print(f"\n📄 Scraping category page {page}...")

        if page > 1:
            time.sleep(delay)

        try:
            response  = session.get(url)
            page_data = response.props_json()
            gig_infos = extract_gig_urls_from_category(page_data)

            if not gig_infos:
                print(f"  ⚠️  No gigs on page {page}, stopping.")
                break

            all_gig_infos.extend(gig_infos)

            if not has_more_pages(page_data):
                print(f"  ℹ️  Fiverr says no more pages after page {page}.")
                break

        except ScraperApiKeyError as e:
            print(f"SCRAPER_ERROR:INVALID_KEY:{e}")
            sys.exit(1)
        except ScraperApiQuotaError as e:
            print(f"SCRAPER_ERROR:QUOTA_EXCEEDED:{e}")
            sys.exit(1)
        except ScraperApiError as e:
            print(f"SCRAPER_ERROR:API_ERROR:{e}")
            sys.exit(1)
        except Exception as e:
            print(f"  ❌ Error on page {page}: {e}")
            import traceback
            traceback.print_exc()
            break

    print(f"\n✅ Total gigs collected: {len(all_gig_infos)}")
    print("=" * 60)

    if not all_gig_infos:
        print("SCRAPER_ERROR:NO_GIGS_FOUND:No gigs were found for this category URL. "
              "Check that the URL is a valid Fiverr category page.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Phase 2 — scrape each individual gig detail page
    # ------------------------------------------------------------------
    scraped_count = 0

    for idx, gig_info in enumerate(all_gig_infos, 1):
        print(f"\n[{idx}/{len(all_gig_infos)}] Processing gig...")
        print(f"  📌 {gig_info['title'][:60]}...")

        gig_details = scrape_gig_details(gig_info, delay=delay)

        if gig_details:
            gig_id      = gig_info.get('gig_id', idx)
            seller_name = sanitize_filename(gig_info.get('seller_name', 'unknown'))
            filename    = f"gig_{gig_id}_{seller_name}.json"
            filepath    = out_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(gig_details, f, indent=2, ensure_ascii=False)

            print(f"  ✅ Saved: {filename}")
            scraped_count += 1
        else:
            print(f"  ⚠️  Skipped (no data)")

    print("\n" + "=" * 60)
    print(f"🎉 Category scrape complete!")
    print(f"   Scraped : {scraped_count}/{len(all_gig_infos)} gigs")
    print(f"   Saved in: {out_dir}")
    print("=" * 60)

    return scraped_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Fiverr Category Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python Fiverr_category-Scrapper.py "https://www.fiverr.com/categories/programming-tech/website-development/custom-websites-development?source=category_filters"
  python Fiverr_category-Scrapper.py "https://www.fiverr.com/categories/programming-tech/website-development/custom-websites-development?source=category_filters" --pages 3
  python Fiverr_category-Scrapper.py "https://..." --pages 2 --key YOUR_API_KEY --delay 3
        '''
    )

    parser.add_argument('url',    help='Fiverr category page URL')
    parser.add_argument('--key',  '-k', help='ScraperAPI key (optional, reads from .env)')
    parser.add_argument('--output', '-o', default='gigs_data', help='Output directory (default: gigs_data)')
    parser.add_argument('--pages',  '-p', type=int, default=1,  help='Pages to scrape (default: 1)')
    parser.add_argument('--delay',  '-d', type=int, default=2,  help='Seconds between requests (default: 2)')

    args = parser.parse_args()

    if 'fiverr.com/categories/' not in args.url:
        print("❌ URL must be a Fiverr category URL.")
        print("   Example: https://www.fiverr.com/categories/programming-tech/website-development/custom-websites-development")
        sys.exit(1)

    scrape_category(
        category_url=args.url,
        api_key=args.key,
        output_dir=args.output,
        max_pages=args.pages,
        delay=args.delay,
    )


if __name__ == '__main__':
    main()
