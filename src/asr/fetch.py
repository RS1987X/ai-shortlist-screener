
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

HEADERS = {"User-Agent": "asr-screener/0.1 (+https://github.com)", "Accept": "text/html"}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
def fetch_html(url: str, timeout: float = 15.0) -> str:
    with httpx.Client(follow_redirects=True, headers=HEADERS, timeout=timeout) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text
