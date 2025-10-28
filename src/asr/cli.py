
import typer
from pathlib import Path
from .audit import audit_urls
from .lar import compute_lar, compute_category_weighted_lar

app = typer.Typer(help="ASR/LAR Screener CLI")

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
