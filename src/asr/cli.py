
import typer
from pathlib import Path
from .audit import audit_urls
from .lar import compute_lar, compute_category_weighted_lar
from .discover import URLDiscoverer
import os

app = typer.Typer(help="ASR/LAR Screener CLI")

@app.command()
def discover(
    intents_csv: str = "data/intents/intents_peer_core_sv.csv",
    peers_csv: str = "data/multibrand_retailer_peers.csv",
    out: str = "data/audit_urls.csv",
    api_key: str = typer.Option(None, envvar="GOOGLE_API_KEY", help="Google Custom Search API key"),
    search_engine_id: str = typer.Option(None, envvar="GOOGLE_SEARCH_ENGINE_ID", help="Google Custom Search Engine ID"),
    use_api: bool = typer.Option(True, help="Use Google API (if configured), otherwise scrape")
):
    """
    Discover product URLs for each intent × peer combination.
    
    Uses site-specific Google searches to minimize bias. Requires Google Custom Search API
    for production use (free tier: 100 queries/day). Falls back to scraping if no API key.
    
    Set environment variables:
      export GOOGLE_API_KEY="your-api-key"
      export GOOGLE_SEARCH_ENGINE_ID="your-cx-id"
    """
    discoverer = URLDiscoverer(api_key=api_key, search_engine_id=search_engine_id)
    
    if use_api and not api_key:
        typer.echo("Warning: No API key provided. Falling back to scraping (slow, may be blocked).")
        typer.echo("Get a free API key: https://developers.google.com/custom-search/v1/overview")
        use_api = False
    
    discoverer.discover_all(intents_csv, peers_csv, out, use_api=use_api)
    typer.echo(f"\n✓ URL discovery complete. Review {out} before running audit.")

@app.command()
def audit(urls_file: str, out: str = "asr_report.csv", follow_children: int = 0):
    urls = Path(urls_file).read_text(encoding="utf-8").splitlines()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    audit_urls(urls, out)
    typer.echo(f"Wrote audit to {out}")

@app.command()
def lar(
    asr_report_csv: str,
    soa_csv: str,
    dist_csv: str,
    service_csv: str,
    out: str = "lar_scores.csv",
    weighted: bool = typer.Option(False, "--weighted", "-w", help="Use category-weighted LAR calculation")
):
    """
    Compute LAR scores from audit and supplementary data.
    
    Use --weighted to enable category-weighted scoring that handles peer category imbalance.
    """
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    
    if weighted:
        compute_category_weighted_lar(asr_report_csv, soa_csv, dist_csv, service_csv, out)
        typer.echo(f"Wrote category-weighted LAR scores to {out}")
    else:
        compute_lar(asr_report_csv, soa_csv, dist_csv, service_csv, out)
        typer.echo(f"Wrote LAR scores to {out}")

if __name__ == "__main__":
    app()
