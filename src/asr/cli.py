
import typer
from pathlib import Path
from .audit import audit_urls
from .lar import compute_lar, compute_category_weighted_lar
from .discover import URLDiscoverer
from .site_search import SiteSearchDiscoverer
from .site_search_playwright import SiteSearchPlaywrightDiscoverer
from .sitemap_search import SitemapSearcher
import os

app = typer.Typer(help="ASR/LAR Screener CLI")

@app.command()
def discover(
    intents_csv: str = "data/intents/intents_peer_core_sv.csv",
    peers_csv: str = "data/multibrand_retailer_peers.csv",
    out: str = "data/audit_urls.csv",
    api_key: str = typer.Option(None, envvar="GOOGLE_API_KEY", help="Google Custom Search API key"),
    search_engine_id: str = typer.Option(None, envvar="GOOGLE_SEARCH_ENGINE_ID", help="Google Custom Search Engine ID"),
    use_sitemap: bool = typer.Option(True, help="Try sitemap search first (respects robots.txt)"),
    use_api: bool = typer.Option(False, help="Use Google API as fallback if sitemap fails"),
    limit: int = typer.Option(10, "--limit", "-n", help="Limit number of searches (default: 10 for development)")
):
    """
    Discover product URLs using sitemap search (primary) with Google API fallback.
    
    Default limit is 10 for development. Remove --limit for full run.
    
    Strategy:
    1. Try sitemap search first (respects robots.txt, no costs)
    2. Fall back to Google API if sitemap not available (100/day free)
    3. Category extraction fallback built-in
    
    Set environment variables for Google API fallback:
      export GOOGLE_API_KEY="your-api-key"
      export GOOGLE_SEARCH_ENGINE_ID="your-cx-id"
    
    Examples:
      asr discover --limit 5          # Test with 5 searches (sitemap)
      asr discover --no-use-sitemap   # Force Google API only
      asr discover --limit 100        # Full run with limit
    """
    
    if use_sitemap:
        # Primary: Use sitemap search
        typer.echo("Using sitemap search (respects robots.txt, no API costs)...")
        try:
            with SitemapSearcher() as searcher:
                searcher.discover_all(intents_csv, peers_csv, out, limit=limit)
            typer.echo(f"\n✓ URL discovery complete. Review {out} before running audit.")
            return
        except Exception as e:
            typer.echo(f"\n⚠ Sitemap search failed: {e}")
            if not use_api:
                typer.echo("No fallback available. Enable --use-api for Google fallback.")
                return
            typer.echo("Falling back to Google API...")
    
    # Fallback: Use Google API
    discoverer = URLDiscoverer(api_key=api_key, search_engine_id=search_engine_id)
    
    if use_api and not api_key:
        typer.echo("Warning: No API key provided. Falling back to scraping (slow, may be blocked).")
        typer.echo("Get a free API key: https://developers.google.com/custom-search/v1/overview")
        use_api = False
    
    discoverer.discover_all(intents_csv, peers_csv, out, use_api=use_api, limit=limit)
    typer.echo(f"\n✓ URL discovery complete. Review {out} before running audit.")

@app.command()
def discover_site(
    intents_csv: str = "data/intents/intents_peer_core_sv.csv",
    peers_csv: str = "data/multibrand_retailer_peers.csv",
    out: str = "data/audit_urls.csv",
    limit: int = typer.Option(None, "--limit", "-n", help="Limit number of searches")
):
    """
    Discover URLs using each retailer's on-site search (NO Google API needed).
    
    This approach:
    - Uses each retailer's own search functionality
    - No API costs or rate limits
    - More accurate product matches
    - Respects site structure
    
    Example:
      asr discover-site --limit 50
    """
    discoverer = SiteSearchDiscoverer()
    discoverer.discover_all(intents_csv, peers_csv, out, limit=limit)
    typer.echo(f"\n✓ URL discovery complete. Review {out} before running audit.")

@app.command()
def discover_playwright(
    intents_csv: str = "data/intents/intents_peer_core_sv.csv",
    peers_csv: str = "data/multibrand_retailer_peers.csv",
    out: str = "data/audit_urls.csv",
    limit: int = typer.Option(None, "--limit", "-n", help="Limit number of searches")
):
    """
    Discover URLs using Playwright for JS-rendered sites (NO Google API needed).
    
    This approach:
    - Uses Playwright for JavaScript rendering
    - Handles dynamic content and SPAs
    - Extracts products from category pages as fallback
    - No API costs or rate limits
    - More accurate for modern JS-heavy sites
    
    Example:
      asr discover-playwright --limit 50
    """
    with SiteSearchPlaywrightDiscoverer() as discoverer:
        discoverer.discover_all(intents_csv, peers_csv, out, limit=limit)
    typer.echo(f"\n✓ URL discovery complete. Review {out} before running audit.")

@app.command()
def audit(urls_file: str, out: str = "asr_report.csv", follow_children: int = 0):
    """
    Audit product URLs to extract structured data.
    
    Accepts either:
    - Plain text file (one URL per line)
    - CSV file with 'url' column (from discover command)
    
    Example:
      asr audit data/audit_urls.csv
      asr audit urls.txt
    """
    import csv
    
    urls = []
    file_content = Path(urls_file).read_text(encoding="utf-8")
    
    # Check if it's a CSV (has header with 'url' column)
    if 'intent_id,brand,domain,url' in file_content or 'url,' in file_content[:200]:
        # It's a CSV, extract URLs from 'url' column
        with open(urls_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('url', '').strip()
                if url and url.startswith('http'):  # Valid URL
                    urls.append(url)
        typer.echo(f"Found {len(urls)} URLs in CSV")
    else:
        # Plain text file
        urls = file_content.splitlines()
        urls = [u.strip() for u in urls if u.strip()]
    
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    audit_urls(urls, out)
    typer.echo(f"Wrote audit to {out}")

@app.command()
def lar(
    asr_report_csv: str,
    soa_csv: str,
    service_csv: str = typer.Option(None, "--service-csv", "-s", help="Optional service/satisfaction scores CSV (if not provided, computed from audit ratings)"),
    out: str = "lar_scores.csv",
    weighted: bool = typer.Option(False, "--weighted", "-w", help="Use category-weighted LAR calculation")
):
    """
    Compute LAR scores from audit and supplementary data.
    
    LAR = 0.40·E + 0.25·X + 0.25·A + 0.10·S
    
    S dimension is auto-computed from product ratings in the audit data.
    Use --service-csv to provide manual overrides (e.g., from Trustpilot, Google Reviews).
    
    Note: D (Distribution) dimension has been removed as it's not applicable 
    to third-party retailers. See docs/methodology.md for details.
    
    Use --weighted to enable category-weighted scoring that handles peer category imbalance.
    
    Examples:
      # Auto-compute S from audit ratings
      asr lar audit.csv soa.csv
      
      # Override with manual satisfaction scores
      asr lar audit.csv soa.csv --service-csv service.csv
      
      # Category-weighted scoring
      asr lar audit.csv soa.csv --weighted
    """
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    
    if weighted:
        compute_category_weighted_lar(asr_report_csv, soa_csv, service_csv, out)
        typer.echo(f"Wrote category-weighted LAR scores to {out}")
    else:
        compute_lar(asr_report_csv, soa_csv, service_csv, out)
        attrib_path = str(Path(out).with_name(Path(out).stem + "_attribution.csv"))
        typer.echo(f"Wrote LAR scores to {out}\nWrote attribution breakdown to {attrib_path}")

if __name__ == "__main__":
    app()
