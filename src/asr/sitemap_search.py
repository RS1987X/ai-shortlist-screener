"""
Sitemap-based URL Discovery - Search product sitemaps for matching products.

Uses retailer sitemaps (respects robots.txt) to find products without
needing search endpoints or JavaScript rendering.
"""

import csv
import gzip
import time
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse
import httpx
from functools import lru_cache


# Known sitemap URLs for retailers
SITEMAP_URLS = {
    "biltema.se": "https://www.biltema.se/globalassets/sitemaps/sitemapindex-sv.xml",
    "bygghemma.se": "https://www.bygghemma.se/sitemap.xml",
    "byggmax.se": "https://www.byggmax.se/pub/media/Sitemap_sv_se_product.xml",
    "clasohlson.com": "https://www.clasohlson.com/sitemap/sitemap_product_se.xml",
    "distit.se": "https://distit.se/sv/wp-sitemap.xml",
    "elgiganten.se": "https://www.elgiganten.se/sitemaps/OCSEELG.pdp.index.sitemap.xml",
    "hornbach.se": "https://www.hornbach.se/sitemap/sitemap.xml",
    "jula.se": "https://www.jula.se/sitemap.1.xml",  # Blocked by Cloudflare (403)
    "netonnet.se": "https://www.netonnet.se/art/sitemap.xml",
    "k-bygg.se": "https://k-bygg.se/sitemap/index.xml",
    "kjell.com": "https://www.kjell.com/sitemap.xml",
    "mekonomen.se": "https://d3sjey3kqst1or.cloudfront.net/media/categories_cms_google_sitemap.xml",
    "rusta.com": "https://www.rusta.com/sitemap.xml?batch=0&language=sv-se",  # Swedish-language product sitemap
    # Cloudflare-blocked (403): dustin.se (https://www.dustin.se/product-sitemap.xml), jula.se
    # No sitemap: beijerbygg.se, alligo.com (no e-commerce)
    # Use --use-api flag for Google API fallback for blocked retailers
}


class SitemapSearcher:
    """Search product sitemaps to find matching URLs."""
    
    def __init__(self, cache_dir: str = ".cache/sitemaps"):
        """
        Initialize sitemap searcher.
        
        Args:
            cache_dir: Directory to cache downloaded sitemaps
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            follow_redirects=True,
        )
        # Cache loaded URLs per domain to avoid reloading for every search
        self._domain_urls_cache: Dict[str, List[str]] = {}
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.client.close()
    
    @lru_cache(maxsize=10)
    def get_sitemap_index(self, domain: str) -> List[str]:
        """
        Get list of sitemap URLs from sitemap index.
        
        Args:
            domain: Retailer domain
        
        Returns:
            List of sitemap URLs
        """
        sitemap_url = SITEMAP_URLS.get(domain)
        if not sitemap_url:
            print(f"  ⚠ No sitemap URL configured for {domain}")
            return []
        
        try:
            resp = self.client.get(sitemap_url)
            resp.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(resp.content)
            
            # Check if this is a sitemap index or a single sitemap
            sitemaps = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            
            if sitemaps:
                # It's an index, return all sitemap URLs
                return [s.text for s in sitemaps]
            else:
                # It's a single sitemap
                return [sitemap_url]
        
        except Exception as e:
            print(f"  Error fetching sitemap index: {e}")
            return []
    
    def is_product_detail_page(self, url: str, sitemap_url: str = None) -> bool:
        """
        Check if a URL is a product detail page (PDP) vs category/listing page.
        
        Strategy: Require positive evidence of a PDP (product ID pattern).
        For sitemaps explicitly named as product/pdp sitemaps, use relaxed filtering.
        
        Args:
            url: URL to check
            sitemap_url: Optional sitemap source URL for context-aware filtering
        
        Returns:
            True if it has a clear product ID pattern or comes from trusted product sitemap
        """
        url_lower = url.lower()
        
        # Check if sitemap indicates high confidence that URLs are products
        # Look for "product", "pdp", or "produkt" in sitemap filename
        relaxed_filter = False
        if sitemap_url:
            sitemap_lower = sitemap_url.lower()
            # Trust sitemaps with explicit product/pdp indicators
            if any(indicator in sitemap_lower for indicator in [
                'product_sitemap', 'product-sitemap', 'pdp',
                'sitemap_product', 'sitemap-product',
                '_product.xml', '-product.xml',
                'produktsitemap', 'produkt-sitemap'
            ]):
                relaxed_filter = True
        
        # Immediate disqualifiers (category/filter indicators) - apply even in relaxed mode
        category_signals = [
            r'/c/',          # Category path
            r'/f/',          # Filter path
            r'\?filter',     # Filter query param
            r'&filter',
            r'\?category',
            r'&category',
        ]
        
        for pattern in category_signals:
            if re.search(pattern, url_lower):
                return False
        
        # Positive PDP patterns: Must have a clear product identifier
        pdp_patterns = [
            # Explicit product ID markers
            r'/p-\d+(?:[/?#]|$)',           # bygghemma.se: /p-1234567
            r'/p/\d+(?:[/?#-]|$)',          # clasohlson: /p/41-2664 (note: allows - after digits for variant)
            r'/p\d{5,}(?:[/?#]|$)',         # kjell.com: /p65105 (5+ digits)
            r'-p\d{5,}(?:[/?#]|$)',         # variant: -p12345
            r'/art-?\d{5,}(?:[/?#]|$)',     # article numbers: /art-12345 or /art12345
            r'/sku-?\d{5,}(?:[/?#]|$)',     # SKU: /sku-12345 or /sku12345
            r'/artikel-\d+(?:[/?#]|$)',     # article: /artikel-123
            r'/produkt/\d+(?:[/?#]|$)',     # product with ID: /produkt/123
            r'/product/[^/]+/\d+(?:[/?#]|$)',  # elgiganten: /product/category/292453
            r'/item-\d+(?:[/?#]|$)',        # item: /item-123
            r'/i-\d+(?:[/?#]|$)',           # short item: /i-123
            
            # URLs ending with long numeric product IDs (7+ digits or long alphanumeric)
            # Matches: /fully-synthetic-engine-oil-0w-20-4-litre-2000035833
            r'-\d{7,}(?:[/?#]|$)',          # ends with 7+ digit product ID
            r'/\d{6,}(?:[/?#]|$)',          # path segment is just 6+ digits
        ]
        
        # Check if URL has a product ID pattern
        has_product_id = any(re.search(p, url_lower) for p in pdp_patterns)
        
        if has_product_id:
            return True
        
        # In relaxed mode (trusted product sitemap), accept slug-only URLs more liberally
        if relaxed_filter:
            parsed = urlparse(url_lower)
            path_segments = [s for s in parsed.path.split('/') if s]
            
            # In relaxed mode, accept 3+ segments (instead of 4+)
            # Example: /kok-och-bad/duscharmatur/duschset-chrome (category/subcat/product)
            if len(path_segments) >= 3:
                last_segment = path_segments[-1]
                # Still reject obvious category endings
                generic_endings = [
                    'products', 'produkter', 'items', 'catalog', 'katalog',
                    'all', 'alla', 'search', 'sok', 'list', 'lista',
                    'categories', 'kategorier'
                ]
                if last_segment not in generic_endings:
                    return True
        
        # Strict fallback for slug-only URLs (e.g., Rusta): Accept if path is deep enough (4+ segments)
        # and doesn't look like a category listing
        # Example: /sv-se/gor-det-sjalv/inomhusfarg/snickeri--och-lackfarg/kvistlack-038-liter
        parsed = urlparse(url_lower)
        path_segments = [s for s in parsed.path.split('/') if s]
        
        # Require at least 4 path segments (lang/cat1/cat2/product) to be considered a product
        if len(path_segments) >= 4:
            # Reject if last segment looks too generic (common category page endings)
            last_segment = path_segments[-1]
            generic_endings = [
                'products', 'produkter', 'items', 'catalog', 'katalog',
                'all', 'alla', 'search', 'sok', 'list', 'lista'
            ]
            if last_segment not in generic_endings:
                return True
        
        return False
    
    def extract_urls_from_sitemap(self, sitemap_url: str) -> List[str]:
        """
        Extract all product URLs from a sitemap.
        
        Args:
            sitemap_url: URL of the sitemap
        
        Returns:
            List of product URLs (filtered to PDPs only)
        """
        try:
            resp = self.client.get(sitemap_url)
            resp.raise_for_status()

            content = resp.content
            
            # Handle compressed content (gzip only - httpx auto-handles brotli if library installed)
            # Check for gzip by URL suffix or magic bytes
            if sitemap_url.endswith('.gz') or (len(content) >= 2 and content[:2] == b'\x1f\x8b'):
                try:
                    content = gzip.decompress(content)
                except Exception:
                    # If server already decompressed due to Accept-Encoding, ignore
                    pass

            root = ET.fromstring(content)

            # If this is a sitemap index (nested sitemaps), return nested URLs recursively
            sitemap_nodes = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if sitemap_nodes:
                all_urls: List[str] = []
                for node in sitemap_nodes:
                    loc = (node.text or '').strip()
                    if not loc:
                        continue
                    all_urls.extend(self.extract_urls_from_sitemap(loc))
                return all_urls

            # Otherwise parse URL set and filter to PDPs only
            urls = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            pdp_urls = [
                url.text for url in urls 
                if url.text and self.is_product_detail_page(url.text, sitemap_url)
            ]
            return pdp_urls

        except Exception as e:
            print(f"  Error fetching sitemap {sitemap_url}: {e}")
            return []
    
    def get_all_product_urls(self, domain: str, limit: Optional[int] = None) -> List[str]:
        """
        Get all product URLs for a domain.
        
        Uses in-memory cache to avoid reloading sitemaps for the same domain.
        
        Args:
            domain: Retailer domain
            limit: Maximum number of sitemaps to fetch (for testing)
        
        Returns:
            List of all product URLs
        """
        # Check cache first
        if domain in self._domain_urls_cache:
            print(f"  ✓ Using cached URLs for {domain} ({len(self._domain_urls_cache[domain])} URLs)")
            return self._domain_urls_cache[domain]
        
        # Not in cache, load from sitemaps
        sitemaps = self.get_sitemap_index(domain)
        
        if limit:
            sitemaps = sitemaps[:limit]
        
        all_urls = []
        for i, sitemap_url in enumerate(sitemaps, 1):
            print(f"  Fetching sitemap {i}/{len(sitemaps)}...", end='\r')
            urls = self.extract_urls_from_sitemap(sitemap_url)
            all_urls.extend(urls)
            time.sleep(0.5)  # Be polite
        
        print(f"  ✓ Loaded {len(all_urls)} product URLs from {len(sitemaps)} sitemaps")
        
        # Cache the results
        self._domain_urls_cache[domain] = all_urls
        
        return all_urls
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for matching."""
        # Lowercase first
        text = text.lower()
        
        # Protect decimals in numbers: "1.5L" should stay "1.5l" not "1 5l"
        # Replace periods NOT between digits with spaces
        text = re.sub(r'\.(?!\d)', ' ', text)  # Replace . not followed by digit
        text = re.sub(r'(?<!\d)\.', ' ', text)  # Replace . not preceded by digit
        
        # Remove other special characters (but keep decimal points within numbers)
        text = re.sub(r'[^\w\s.-]', ' ', text)
        
        # Normalize spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract_search_terms(self, intent: Dict) -> List[str]:
        """
        Extract search terms from intent.
        
        Args:
            intent: Intent dict with prompt, category, constraints
        
        Returns:
            List of search terms (keywords to match)
        """
        prompt = intent.get("prompt", "")
        category = intent.get("category", "")
        constraints = intent.get("constraints", "")
        
        # Get product type from prompt/category
        product_type = category.replace('-', ' ') if category else ""

        # Extract key descriptive terms from prompt (first few words)
        prompt_clean = re.sub(r'under\s+\d+\s*kr.*', '', prompt or "")  # Remove price hints
        prompt_clean = re.sub(r'\d+[×x]', '', prompt_clean)  # Remove quantities like 2x/3×
        # Normalize common tokens: wi-fi -> wifi; fix superscripts m²/m³ -> m2/m3
        prompt_clean = re.sub(r'\bwi[-\s]?fi\b', 'wifi', prompt_clean, flags=re.IGNORECASE)
        prompt_clean = prompt_clean.replace('m²','m2').replace('m³','m3')

        # Filter out stopwords, pure numbers, and unit-only tokens from prompt words
        swedish_stopwords = {'med', 'och', 'för', 'till', 'som', 'i', 'på', 'av', 'från', 'enl'}
        UNIT_TOKENS_LOCAL = {
            'mm','cm','m','l','cl','dl','ml','hz','khz','mhz','ghz','w','kw','v','kv',
            'mah','ah','gb','mb','tb','lm','db','bar','tum','k','kwh'
        }
        words_all = self.normalize_text(prompt_clean).split()
        words = []
        for w in words_all:
            if w in swedish_stopwords:
                continue
            # skip pure numeric tokens (e.g., "20", "000", "1.5")
            if re.fullmatch(r'\d+(?:\.\d+)?', w):
                continue
            # skip unit-only tokens without numbers (e.g., "mah", "w")
            if w in UNIT_TOKENS_LOCAL:
                continue
            words.append(w)
        words = words[:4]

        # Extract specs (numeric + unit) from prompt, category, and constraints
        specs = []
        combined_for_specs = ' '.join(filter(None, [prompt, category, constraints]))
        # Normalize common tokens: wi-fi -> wifi; fix superscripts m²/m³ -> m2/m3
        combined_for_specs = re.sub(r'\bwi[-\s]?fi\b', 'wifi', combined_for_specs, flags=re.IGNORECASE)
        combined_for_specs = combined_for_specs.replace('m²','m2').replace('m³','m3')
        # Normalize spaces inside numbers: "20 000 mAh" -> "20000 mAh"
        combined_for_specs = re.sub(r'(\d+)\s+(\d+)', r'\1\2', combined_for_specs)
        # Numeric specs (e.g., 20000mah, 4k, 100w, 1.5l, 240hz, 500gb, 300mbps)
        UNIT_PATTERN = (
            r'mah|ah|wh|watt|w|kw|va|v|mv|kv|a|ma|hz|khz|mhz|ghz|db|lm|lux|cd|'
            r'k|kb|mb|gb|tb|bps|mbps|gbps|l|dl|cl|ml|m2|m3|m|cm|mm|um|nm|km|'
            r'in|inch|ft|tum'
        )
        numeric_specs = re.findall(rf'\b\d+(?:\.\d+)?\s*(?:{UNIT_PATTERN})\b', combined_for_specs, re.IGNORECASE)
        # e.g., "20000mah" or "1.5l"
        specs.extend([self.normalize_text(s).replace(' ', '') for s in numeric_specs])

        # Standards (USB-C, HDMI, PD, etc.)
        standards = re.findall(r'\b(?:usb-c|usb|hdmi|pd|ip\d+|ax\d+|ips|hepa)\b', combined_for_specs, re.IGNORECASE)
        specs.extend([self.normalize_text(s) for s in standards])

        # Additionally, include the pure numeric part of each spec (e.g., "20000" from "20000mah")
        numeric_only = []
        for s in specs:
            m = re.match(r'^(\d+(?:\.\d+)?)', s)
            if m:
                numeric_only.append(m.group(1))

        # Deduplicate while preserving order
        seen = set()
        specs_dedup = []
        for s in specs + numeric_only:
            if s not in seen:
                seen.add(s)
                specs_dedup.append(s)

        # Combine: product type + descriptive words + up to 4 spec tokens (including numeric-only)
        terms = [product_type] + words + specs_dedup[:4]
        return [t for t in terms if t and len(t) > 1]  # Filter empty/short terms
    
    def score_url(self, url: str, search_terms: List[str]) -> Tuple[float, Dict]:
        """
        Score how well a URL matches search terms.
        
        Args:
            url: Product URL to score
            search_terms: List of keywords to match
        
        Returns:
            (score, details) tuple
        """
        url_text = self.normalize_text(url)
        # Also normalize spaces in numbers for matching (20 000 -> 20000)
        url_normalized = re.sub(r'(\d+)\s+(\d+)', r'\1\2', url_text)
        
        score = 0.0
        matched_terms = []
        
        for i, term in enumerate(search_terms):
            matched = False
            
            # Check both original and normalized URL
            if term in url_text or term in url_normalized:
                matched = True
            else:
                # For multi-word terms (e.g., "coffee machine"), also try without space
                if ' ' in term:
                    term_no_space = term.replace(' ', '')
                    if term_no_space in url_text or term_no_space in url_normalized:
                        matched = True
            
            if matched:
                # First term (product type/category) gets higher weight
                weight = 2.0 if i == 0 else 1.0
                
                # Numeric specs (with numbers) get extra weight for exact matches
                if re.search(r'\d+', term):
                    weight += 1.0
                
                score += weight
                matched_terms.append(term)
        
        # Bonus for matching multiple terms
        if len(matched_terms) >= 2:
            score += 0.5
        
        # Bonus for category match (if URL has /category/ structure)
        if search_terms and search_terms[0]:
            category_variants = [
                f"/{search_terms[0].replace(' ', '-')}/",
                f"/{search_terms[0].replace(' ', '')}/",
                f"/{search_terms[0].split()[0]}/"  # First word of category
            ]
            if any(variant in url_text for variant in category_variants):
                score += 1.0
        
        details = {
            'matched_terms': matched_terms,
            'match_count': len(matched_terms),
        }
        
        return score, details
    
    def search(self, domain: str, intent: Dict, top_k: int = 10) -> List[Dict]:
        """
        Search sitemaps for products matching intent.
        
        Strategy:
        1. Try to match products with category + specs (numeric terms)
        2. If no good spec matches found, fall back to category + descriptive terms
        3. Always return results if the category exists
        
        Args:
            domain: Retailer domain
            intent: Intent dict
            top_k: Number of top results to return
        
        Returns:
            List of dicts with 'url', 'score', 'matched_terms'
        """
        # Get search terms
        search_terms = self.extract_search_terms(intent)
        if not search_terms:
            print(f"  ⚠ No search terms extracted from intent")
            return []
        
        print(f"  Search terms: {', '.join(search_terms[:5])}")
        
        # Identify category, descriptive, and spec terms
        category_term = search_terms[0] if search_terms else None
        spec_terms = [t for t in search_terms if re.search(r'\d+', t)]  # Terms with numbers
        descriptive_terms = [t for t in search_terms[1:] if not re.search(r'\d+', t)]  # Words without numbers
        # Any term without digits is a candidate non-numeric term (category, standards like usb-c/hdmi)
        non_numeric_terms = [t for t in search_terms if not re.search(r'\d+', t)]

        # Define unit tokens that should NOT count as anchors by themselves (avoid 'mm' in '32mm')
        UNIT_TOKENS = {
            'mm','cm','m','l','cl','dl','ml','hz','khz','mhz','ghz','w','kw','v','kv',
            'mah','ah','gb','mb','tb','lm','db','bar','tum','k','kwh'
        }
        # Allow a few short-but-meaningful anchors
        SHORT_ANCHORS = {'usb','hdmi','pd','m2','wifi','mesh'}
        anchor_terms = [t for t in non_numeric_terms if (len(t) >= 3 or t in SHORT_ANCHORS) and t not in UNIT_TOKENS]
        
        # Get all product URLs from all sitemaps
        all_urls = self.get_all_product_urls(domain, limit=None)
        
        if not all_urls:
            return []
        
        # Score each URL
        scored_results = []
        category_only_results = []  # Fallback: products matching category + descriptive terms
        
        for url in all_urls:
            score, details = self.score_url(url, search_terms)
            if score > 0:
                # Guardrail: require at least one non-numeric ANCHOR match (exclude bare unit tokens like 'mm')
                # Avoid numeric-only matches like 32mm/30m that trigger on units but don't match category/descriptor
                has_non_numeric_match = any(t in details['matched_terms'] for t in anchor_terms)
                if not has_non_numeric_match:
                    # Skip numeric-only matches
                    continue

                result = {
                    'url': url,
                    'score': score,
                    'matched_terms': details['matched_terms'],
                    'match_count': details['match_count'],
                }
                scored_results.append(result)

                # Track category+descriptive matches (no specs) for fallback
                if category_term and category_term in details['matched_terms']:
                    has_spec_match = any(spec in details['matched_terms'] for spec in spec_terms)
                    has_descriptive_match = any(desc in details['matched_terms'] for desc in descriptive_terms)

                    # Good category match: has category + descriptive terms but no specs
                    if not has_spec_match and has_descriptive_match:
                        category_only_results.append(result)
        
        # Sort by score
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        category_only_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Check quality of top results
        if scored_results:
            top_results = scored_results[:top_k]
            
            # Count how many top results have spec matches
            spec_match_count = sum(
                1 for r in top_results
                if any(spec in r['matched_terms'] for spec in spec_terms)
            )
            
            # If specs were requested but less than 50% of top results have them
            if spec_terms and spec_match_count < len(top_results) * 0.5:
                print(f"  ⚠ Warning: Only {spec_match_count}/{len(top_results)} top results match specs {spec_terms}")
                
                # If we have good category+descriptive matches, prefer those
                if category_only_results and len(category_only_results) >= top_k * 0.5:
                    print(f"  ℹ Falling back to {len(category_only_results)} category+descriptive matches")
                    print(f"    (Specs {spec_terms} not found in URLs)")
                    return category_only_results[:top_k]
                else:
                    print(f"  ℹ Keeping mixed results (specs may not be in URLs)")
            
            print(f"  ✓ Found {len(scored_results)} matching URLs")
            return top_results
        else:
            print(f"  ⚠ No matches found for any search terms")
            return []
    
    def discover_url(self, intent: Dict, peer_domain: str, peer_brand: str) -> Optional[Dict]:
        """
        Discover best product URL for intent using sitemap search.
        
        Args:
            intent: Intent dict
            peer_domain: Peer domain
            peer_brand: Peer brand name
        
        Returns:
            Dict with 'url', 'score', 'title', 'search_query' or None
        """
        results = self.search(peer_domain, intent, top_k=1)
        
        if results:
            best = results[0]
            # Extract product name from URL for title
            url_parts = best['url'].rstrip('/').split('/')
            title = url_parts[-2] if len(url_parts) >= 2 else ""
            title = title.replace('-', ' ').title()
            
            return {
                'url': best['url'],
                'score': best['score'] / 10.0,  # Normalize to 0-1 range
                'title': title,
                'search_query': f"sitemap:{peer_domain} {' '.join(self.extract_search_terms(intent)[:3])}",
            }
        
        return None
    
    def discover_all(
        self,
        intents_csv: str,
        peers_csv: str,
        output_csv: str,
        limit: Optional[int] = None,
    ) -> None:
        """
        Discover URLs for all intent × peer combinations using sitemaps.
        
        Args:
            intents_csv: Path to intents CSV
            peers_csv: Path to peers CSV
            output_csv: Output path
            limit: Max number of searches (for testing)
        """
        # Load intents
        intents = []
        with open(intents_csv, encoding="utf-8") as f:
            intents = list(csv.DictReader(f))
        
        # Load peers
        peers = []
        with open(peers_csv, encoding="utf-8") as f:
            peers = list(csv.DictReader(f))
        
        results = []
        total = len(intents) * len(peers)
        count = 0
        searches_performed = 0
        
        for intent in intents:
            intent_id = intent.get("intent_id")
            
            for peer in peers:
                count += 1
                
                if limit and searches_performed >= limit:
                    print(f"\n⚠ Limit of {limit} searches reached")
                    break
                
                brand = peer.get("brand")
                domain = peer.get("domain")
                
                print(f"\n[{count}/{total}] Sitemap search: {brand} for {intent_id}")
                
                try:
                    result = self.discover_url(intent, domain, brand)
                    searches_performed += 1
                    
                    if result:
                        results.append({
                            "intent_id": intent_id,
                            "brand": brand,
                            "domain": domain,
                            "url": result['url'],
                            "relevance_score": round(result['score'], 2),
                            "title": result['title'],
                            "search_query": result['search_query'],
                            "found": 1,
                        })
                    else:
                        search_terms = self.extract_search_terms(intent)
                        results.append({
                            "intent_id": intent_id,
                            "brand": brand,
                            "domain": domain,
                            "url": "",
                            "relevance_score": 0.0,
                            "title": "",
                            "search_query": f"sitemap:{domain} {' '.join(search_terms[:3])}",
                            "found": 0,
                        })
                
                except Exception as e:
                    print(f"  Error: {e}")
                    results.append({
                        "intent_id": intent_id,
                        "brand": brand,
                        "domain": domain,
                        "url": "",
                        "relevance_score": 0.0,
                        "title": "",
                        "search_query": "",
                        "found": 0,
                    })
            
            if limit and searches_performed >= limit:
                break
        
        # Write output
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["intent_id", "brand", "domain", "url", "relevance_score", "title", "search_query", "found"])
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\n\nWrote {len(results)} URL mappings to {output_csv}")
        found = sum(1 for r in results if r.get("found"))
        print(f"Found: {found}/{len(results)} ({100*found/len(results):.1f}%)")
