from typing import Optional, Tuple

from playwright.sync_api import sync_playwright
import extruct
from w3lib.html import get_base_url

from .parse import extract_jsonld, classify_schema
from .parse import extract_ratings_fallback as extract_fallback_from_html

# Small, general JS-rendering fallback that avoids site-specific logic.
# Strategy:
# 1) Render page with Playwright (Chromium), wait for network idle
# 2) Re-run JSON-LD extraction on rendered HTML
# 3) Try embedded JSON/inline fallback on rendered HTML
# 4) Try Microdata/RDFa AggregateRating from extruct (rendered HTML)
# Returns (rating_value, rating_count, source) or None

def _extract_from_items(items) -> Optional[Tuple[str, str]]:
    # Mirror the minimal AggregateRating scan used in audit.py, but without side-effects
    # Buckets for convenience
    buckets = {"Product": [], "AggregateRating": []}
    for it in items:
        t = it.get("@type")
        if isinstance(t, list):
            t = next((x for x in t if isinstance(x, str)), None)
        if not isinstance(t, str):
            continue
        if t == "Product":
            buckets["Product"].append(it)
        elif t == "AggregateRating":
            buckets["AggregateRating"].append(it)

    # Build @id index to resolve references
    id_index = {}
    for it in items:
        _id = it.get("@id")
        if isinstance(_id, str):
            id_index[_id] = it

    def _resolve(value):
        if value is None:
            return []
        if isinstance(value, list):
            out = []
            for v in value:
                out.extend(_resolve(v))
            return out
        if isinstance(value, dict):
            ref = value.get("@id")
            if isinstance(ref, str) and ref in id_index:
                return [id_index[ref]]
            return [value]
        if isinstance(value, str) and value in id_index:
            return [id_index[value]]
        return []

    # Product.aggregateRating
    for p in buckets["Product"]:
        agg = p.get("aggregateRating")
        for ar in _resolve(agg) or []:
            if isinstance(ar, dict):
                rv = ar.get("ratingValue")
                rc = ar.get("ratingCount") or ar.get("reviewCount")
                if rv is not None:
                    return str(rv), str(rc or "")

    # Standalone AggregateRating
    for ar in buckets["AggregateRating"]:
        rv = ar.get("ratingValue")
        rc = ar.get("ratingCount") or ar.get("reviewCount")
        if rv is not None:
            return str(rv), str(rc or "")

    return None


def extract_ratings_js(url: str, timeout_ms: int = 20000) -> Optional[Tuple[str, str, str]]:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                # If networkidle never comes, proceed with current DOM
                pass
            html = page.content()
            browser.close()
    except Exception:
        return None

    # 1) JSON-LD after JS
    items = extract_jsonld(html, url)
    if items:
        found = _extract_from_items(items)
        if found:
            rv, rc = found
            return rv, rc, "playwright-jsonld"

    # 2) Embedded JSON/inline in rendered HTML
    fb = extract_fallback_from_html(html)
    if fb:
        rv, rc, _ = fb
        # rewrite source to indicate JS path
        source = "playwright-application/json" if _ == "application/json" else "playwright-inline_js"
        return rv, rc, source

    # 3) Microdata/RDFa from rendered HTML
    try:
        base = get_base_url(html, url)
        data = extruct.extract(
            html,
            base_url=base,
            syntaxes=["microdata", "rdfa"],
            errors="ignore"
        )
        # extruct returns dict with keys 'microdata', 'rdfa'
        for key in ("microdata", "rdfa"):
            for it in data.get(key, []) or []:
                # extruct formats microdata differently; normalize a bit
                if isinstance(it, dict):
                    # look for AggregateRating-like
                    types = it.get("type") or it.get("@type")
                    if isinstance(types, list):
                        types = next((t for t in types if isinstance(t, str)), None)
                    if types in ("AggregateRating",):
                        rv = it.get("properties", {}).get("ratingValue") if it.get("properties") else it.get("ratingValue")
                        rc = None
                        if it.get("properties"):
                            rc = it["properties"].get("ratingCount") or it["properties"].get("reviewCount")
                        else:
                            rc = it.get("ratingCount") or it.get("reviewCount")
                        if rv is not None:
                            return str(rv), str(rc or ""), f"playwright-{key}"
    except Exception:
        pass

    return None
