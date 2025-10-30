
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,sv;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
def fetch_html(url: str, timeout: float = 15.0) -> str:
    with httpx.Client(follow_redirects=True, headers=HEADERS, timeout=timeout) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text
