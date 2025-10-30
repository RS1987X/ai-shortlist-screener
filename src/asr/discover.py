"""
URL Discovery Module - Find product URLs for intents without bias.

Uses site-specific Google searches to find the best-matching product
from each peer for each intent, minimizing cross-site ranking bias.
"""

import csv
import time
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class URLDiscoverer:
    """Discovers product URLs for intent × peer combinations via unbiased search."""
    
    def __init__(self, api_key: Optional[str] = None, search_engine_id: Optional[str] = None):
        """
        Initialize URL discoverer.
        
        Args:
            api_key: Google Custom Search API key (optional, falls back to scraping)
            search_engine_id: Google Custom Search Engine ID (optional)
        """
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def extract_search_terms(self, intent: Dict) -> str:
        """
        Extract search keywords from intent constraints.
        
        Args:
            intent: Intent dict with 'prompt', 'constraints', 'category'
        
        Returns:
            Search query string (without brand names to avoid bias)
        """
        # Extract product type from prompt (first few words before specs/price)
        prompt = intent.get("prompt", "")
        
        # Remove price constraints and quantities from prompt
        prompt_clean = re.sub(r"under\s+\d+[\s,]?\d*\s*kr.*", "", prompt, flags=re.IGNORECASE)
        prompt_clean = re.sub(r'\d+[×x]', '', prompt_clean)  # Remove quantity prefixes like "2×"
        prompt_clean = re.sub(r'\d+K\d+', lambda m: m.group()[:2] + 'K', prompt_clean)  # 4K60 -> 4K
        prompt_clean = re.sub(r'\s+', ' ', prompt_clean).strip()  # Normalize spaces
        
        # Take first 2-3 words from prompt as product type, remove Swedish stop words
        swedish_stopwords = {'med', 'och', 'för', 'till', 'som', 'i', 'på', 'av', 'från', 'W'}
        product_words = [w for w in prompt_clean.split()[:6] if w.lower() not in swedish_stopwords][:3]
        product_type = " ".join(product_words).strip()
        
        # Normalize hyphens between words (USB-C-hub -> USB-C hub)
        product_type = re.sub(r'-(\w+hub|station|docka)', r' \1', product_type, flags=re.IGNORECASE)
        
        # Extract key specs from constraints (remove price, brand references)
        constraints = intent.get("constraints", "")
        
        # Remove quantity prefixes and noise from constraints
        clean_constraints = re.sub(r'\d+[×x]', '', constraints)  # Remove "2×" from "2×HDMI"
        
        # Remove common noise words
        noise_patterns = [
            r"pris\s*<.*?kr",  # price constraints
            r"under\s+\d+\s*kr",
            r"enl\.\s*PDP",
            r"enligt\s+PDP",
            r"flygsäker",  # feature flags without specs
        ]
        
        for pattern in noise_patterns:
            clean_constraints = re.sub(pattern, "", clean_constraints, flags=re.IGNORECASE)
        
        # Extract technical specs with normalization and deduplication
        spec_list = []
        seen_upper = set()
        
        # 1. Resolution specs (4K60 -> 4K, 1080p60 -> 1080p)
        resolutions = re.findall(r'\d+K\d*', clean_constraints, flags=re.IGNORECASE)
        for res in resolutions:
            normalized = re.sub(r'(\d+K)\d*', r'\1', res, flags=re.IGNORECASE).upper()
            if normalized not in seen_upper:
                spec_list.append(normalized)
                seen_upper.add(normalized)
        
        # 2. Power/capacity specs (100W, 20000mAh, etc.)
        power_specs = re.findall(r'\d+\s*(?:W|mAh|V|Hz|bar|kg|GB|TB|dB|lm)\b', clean_constraints, flags=re.IGNORECASE)
        for spec in power_specs:
            spec_clean = spec.replace(' ', '').upper()
            if spec_clean not in seen_upper:
                spec_list.append(spec_clean)
                seen_upper.add(spec_clean)
        
        # 3. Standards (HDMI, USB-C, PD, IP65, etc.) - only unique ones
        standards = re.findall(r'\b(?:HDMI|USB-C|USB|PD|IP\d+|AX\d+|S\d+|IPS|HEPA|CE)\b', clean_constraints, flags=re.IGNORECASE)
        for std in standards:
            std_upper = std.upper()
            if std_upper not in seen_upper:
                spec_list.append(std)
                seen_upper.add(std_upper)
        
        # Combine product type + key specs (limit to avoid over-specification)
        query_parts = [product_type] + spec_list[:5]
        return " ".join(query_parts).strip()
    
    def build_site_query(self, domain: str, search_terms: str) -> str:
        """
        Build site-specific Google search query.
        
        Args:
            domain: Peer domain (e.g., 'clasohlson.com')
            search_terms: Search keywords
        
        Returns:
            Query string for Google
        """
        return f"site:{domain} {search_terms}"
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def search_google_custom(self, query: str, num_results: int = 5) -> List[Dict]:
        """
        Search using Google Custom Search API (if configured).
        
        Args:
            query: Search query
            num_results: Number of results to fetch
        
        Returns:
            List of result dicts with 'url', 'title', 'snippet'
        """
        if not self.api_key or not self.search_engine_id:
            return []
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": min(num_results, 10),
            "gl": "se",  # Sweden
            "hl": "sv",  # Swedish
        }
        
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        
        results = []
        for item in data.get("items", []):
            results.append({
                "url": item.get("link"),
                "title": item.get("title"),
                "snippet": item.get("snippet", ""),
            })
        
        return results
    
    def search_google_scrape(self, query: str, num_results: int = 5) -> List[Dict]:
        """
        Fallback: Scrape Google search results (use sparingly, rate limited).
        
        Args:
            query: Search query
            num_results: Number of results to attempt
        
        Returns:
            List of result dicts with 'url', 'title', 'snippet'
        """
        # Note: This is a simplified scraper. In production, use official API or SerpAPI.
        # Scraping Google violates ToS and may get blocked.
        
        results = []
        url = "https://www.google.com/search"
        params = {
            "q": query,
            "num": num_results,
            "gl": "se",
            "hl": "sv",
            "pws": "0",  # Disable personalization
        }
        
        try:
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                
                # Very basic parsing - extract URLs from result divs
                # This is fragile and for demo only. Use official API in production.
                import re
                pattern = r'<a href="/url\?q=(https?://[^&]+)&amp;'
                matches = re.findall(pattern, resp.text)
                
                for match in matches[:num_results]:
                    # Decode URL
                    from urllib.parse import unquote
                    clean_url = unquote(match)
                    results.append({
                        "url": clean_url,
                        "title": "",
                        "snippet": "",
                    })
        
        except Exception as e:
            print(f"Scrape failed for query '{query}': {e}")
        
        return results
    
    def score_url_relevance(self, url: str, intent: Dict, result: Dict) -> float:
        """
        Score how well a URL matches the intent (0-1).
        
        Checks URL path, title, snippet for intent keywords.
        Requires product page indicators to avoid category/listing pages.
        
        Args:
            url: Product page URL
            intent: Intent dict
            result: Search result dict with 'title', 'snippet'
        
        Returns:
            Relevance score 0-1 (0 if not a product page)
        """
        url_lower = url.lower()
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        
        # 1. Check for strong product page signals
        strong_product_indicators = [
            "/product/", "/produkt/", "/p/", "/art/", "/artikel/",
            "-p-", "/item/", "/pd/", "/products/"
        ]
        has_strong_indicator = any(ind in url_lower for ind in strong_product_indicators)
        
        # 2. Check if URL ends with a product ID pattern
        # Product pages typically end with: /product-name-12345 or /product-name/12345
        # Look for numeric IDs (4+ digits) at the end, possibly with trailing slash
        has_product_id = bool(re.search(r'[/-]\d{4,}/?$', path))
        
        # 3. Check for alphanumeric SKU/product codes at the end
        # e.g., /product-name-cb1022-p65980 or /belkin-hub-ABC123
        # Must start with letters, then have letter-digit pattern (not just digit-letter like "31-tum")
        has_product_code = bool(re.search(r'[/-][a-z]{2,}[0-9]+-[a-z]\d+[a-z0-9]*/?$', path, re.IGNORECASE))
        
        # 4. Detect category/listing page patterns (GENERIC)
        category_indicators = [
            # Generic category paths
            r'/category/', r'/categories/', r'/kategori/', r'/kategorier/',
            r'/catalog/', r'/catalogue/', r'/katalog/',
            r'/browse/', r'/shop/', r'/products/?$',  # "/products" without ID
            
            # Listing/filter pages (ends with generic terms, no product ID)
            r'/[a-z-]+/?$',  # Generic path segment without numbers at the end
        ]
        
        # Check if path segments indicate category structure without product
        # Category pages often have 2-4 segments like /electronics/computers/laptops
        # Product pages add a 5th segment with ID: /electronics/computers/laptops/dell-laptop/12345
        path_segments = [s for s in path.split('/') if s]
        
        # If last segment is just a category name (no numbers), likely a category page
        last_segment = path_segments[-1] if path_segments else ""
        is_category_name_only = bool(last_segment and not re.search(r'\d', last_segment) and len(last_segment) > 3)
        
        # Check for category/filter patterns in last segment (e.g., "31-tum-storre", "datorskarmar-kategorier")
        category_suffix_patterns = [
            r'-\d+-tum',  # Size filters: "31-tum-storre"
            r'-storre$',  # "större" (larger)
            r'-mindre$',  # "mindre" (smaller)
            r'-kategorier$',  # "categories"
            r'-kategori$',
        ]
        has_category_suffix = any(re.search(pattern, last_segment) for pattern in category_suffix_patterns)
        
        # If URL has 2-3 segments with no product ID/code, likely a category page
        is_shallow_category = len(path_segments) <= 3 and not has_product_id and not has_product_code
        
        # 5. Title/snippet analysis for category page signals
        text = " ".join([
            result.get("title", "").lower(),
            result.get("snippet", "").lower(),
        ])
        
        # Category pages often have these phrases in title
        category_title_patterns = [
            r'\d+\s*produkter',  # "N produkter" (any number + "produkter", e.g., "245 produkter")
            r'\d+\s*products',   # "N products" (e.g., "132 products")
            r'visa\s+alla',      # "visa alla" (show all)
            r'show\s+all',       # "show all"
            r'browse\s+',        # "browse ..."
            r'category:',        # "category:"
            r'kategori:',        # "kategori:"
        ]
        has_category_title = any(re.search(pattern, text) for pattern in category_title_patterns)
        
        # 6. Decision logic
        # Strong product page: has indicator AND (product ID OR product code)
        is_product_page = has_strong_indicator and (has_product_id or has_product_code)
        
        # Category page signals
        is_likely_category = (
            is_category_name_only or 
            has_category_suffix or
            is_shallow_category or 
            has_category_title or
            any(re.search(pattern, url_lower) for pattern in category_indicators[:6])  # Generic patterns only
        )
        
        # If likely category and no strong product signals, reject
        if is_likely_category and not is_product_page:
            return 0.0
        
        # If no product indicators at all, reject
        if not has_strong_indicator and not has_product_id and not has_product_code:
            return 0.0
        
        # 7. Now score the actual relevance (only for confirmed product pages)
        score = 0.0
        
        # Extract key terms from intent
        category = intent.get("category", "").lower()
        constraints = intent.get("constraints", "").lower()
        
        # Combine searchable text (URL + title + snippet)
        full_text = " ".join([
            url_lower,
            text,
        ])
        
        # Score based on category match
        if category and category in full_text:
            score += 0.3
        
        # Score based on key specs present
        key_specs = re.findall(r'\d+[×x]\d+|\d+\s*(?:mm|cm|L|W|V|Hz|GB|mAh|bar)', constraints)
        if key_specs:
            matches = sum(1 for spec in key_specs if spec.lower() in full_text)
            score += 0.4 * (matches / len(key_specs))
        
        # Bonus for strong product page signals
        if has_strong_indicator:
            score += 0.2
        if has_product_id or has_product_code:
            score += 0.1
        
        return min(score, 1.0)
    
    def extract_product_from_category_page(self, category_url: str, domain: str, intent: Dict) -> Optional[Dict]:
        """
        Fallback: Extract first valid product link from a category page.
        
        When Google returns a category page instead of a product page,
        try to extract product links from that category page.
        
        Args:
            category_url: URL of the category page
            domain: Expected domain
            intent: Intent dict (for scoring products)
        
        Returns:
            Dict with 'url', 'title', 'score' or None if no products found
        """
        try:
            print(f"  📂 Extracting products from category page...")
            
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True) as client:
                resp = client.get(category_url)
                resp.raise_for_status()
                html = resp.text
            
            # Extract all links
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=True)
            
            products = []
            seen_urls = set()
            
            for link in links[:100]:  # Check first 100 links
                href = link.get('href', '')
                if not href:
                    continue
                
                # Make absolute URL
                from urllib.parse import urljoin
                if href.startswith('/'):
                    href = urljoin(f"https://{domain}", href)
                elif not href.startswith('http'):
                    continue
                
                # Check if it's a product page
                parsed = urlparse(href)
                result_domain = parsed.netloc.replace('www.', '')
                expected_domain = domain.replace('www.', '')
                
                if result_domain != expected_domain:
                    continue
                
                # Score this URL
                fake_result = {'title': link.get_text(strip=True), 'snippet': ''}
                score = self.score_url_relevance(href, intent, fake_result)
                
                # Only accept product pages (score > 0)
                if score > 0 and href not in seen_urls:
                    seen_urls.add(href)
                    products.append({
                        'url': href,
                        'title': fake_result['title'],
                        'score': score,
                    })
                
                if len(products) >= 10:
                    break
            
            if products:
                # Return best product
                best = max(products, key=lambda x: x['score'])
                print(f"  ✓ Extracted {len(products)} products, best score: {best['score']:.2f}")
                return best
            
            print(f"  ✗ No product links found on category page")
            return None
        
        except Exception as e:
            print(f"  ✗ Category extraction failed: {e}")
            return None
    
    def discover_url(
        self,
        intent: Dict,
        peer_domain: str,
        peer_brand: str,
        use_api: bool = True
    ) -> Optional[Dict]:
        """
        Discover best product URL for an intent × peer combination.
        
        Args:
            intent: Intent dict from intents CSV
            peer_domain: Peer's domain (e.g., 'clasohlson.com')
            peer_brand: Peer's brand name
            use_api: Use Google API if available, else scrape
        
        Returns:
            Dict with 'url', 'score', 'title', 'search_query' or None if not found
        """
        search_terms = self.extract_search_terms(intent)
        query = self.build_site_query(peer_domain, search_terms)
        
        # Search
        if use_api and self.api_key:
            results = self.search_google_custom(query, num_results=5)
        else:
            # Fallback to scraping (add delay to avoid rate limits)
            time.sleep(2)  # Be respectful
            results = self.search_google_scrape(query, num_results=5)
        
        if not results:
            return None
        
        # Score and rank results by relevance
        scored_results = []
        for result in results:
            url = result.get("url")
            if not url:
                continue
            
            # Filter out non-product pages
            parsed = urlparse(url)
            # Check domain match (handle www. prefix)
            result_domain = parsed.netloc.replace('www.', '')
            expected_domain = peer_domain.replace('www.', '')
            if result_domain != expected_domain:
                continue  # Skip if wrong domain
            
            score = self.score_url_relevance(url, intent, result)
            scored_results.append({
                "url": url,
                "score": score,
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "search_query": query,
            })
        
        # Return best match
        if scored_results:
            best = max(scored_results, key=lambda x: x["score"])
            
            # If best result has score 0 (likely category page), try extraction fallback
            if best["score"] == 0.0 and best["url"]:
                print(f"  ⚠ Top result appears to be category page (score=0), trying extraction...")
                extracted = self.extract_product_from_category_page(best["url"], peer_domain, intent)
                if extracted:
                    return {
                        "url": extracted["url"],
                        "score": extracted["score"],
                        "title": extracted["title"],
                        "search_query": query + " [category-extraction]",
                    }
            
            return best
        
        return None
    
    def discover_all(
        self,
        intents_csv: str,
        peers_csv: str,
        output_csv: str,
        use_api: bool = True,
        limit: Optional[int] = None,
    ) -> None:
        """
        Discover URLs for all intent × peer combinations.
        
        Args:
            intents_csv: Path to intents CSV
            peers_csv: Path to peers CSV
            output_csv: Output path for audit_urls.csv
            use_api: Use Google API if configured
            limit: Maximum number of searches to perform (None = unlimited)
        """
        # Load intents
        intents = []
        with open(intents_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                intents.append(row)
        
        # Load peers
        peers = []
        with open(peers_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                peers.append(row)
        
        # Discover URLs
        results = []
        total = len(intents) * len(peers)
        count = 0
        searches_performed = 0
        
        for intent in intents:
            intent_id = intent.get("intent_id")
            
            for peer in peers:
                count += 1
                
                # Check if limit reached
                if limit and searches_performed >= limit:
                    print(f"\n⚠ Limit of {limit} searches reached. Stopping.")
                    print(f"Progress: {count-1}/{total} combinations processed")
                    print(f"Resume by running with updated --limit or remove limit for full run")
                    break
                
                brand = peer.get("brand")
                domain = peer.get("domain")
                
                print(f"[{count}/{total}] Searching {brand} for {intent_id}...")
                
                try:
                    result = self.discover_url(intent, domain, brand, use_api=use_api)
                    searches_performed += 1
                    
                    if result:
                        results.append({
                            "intent_id": intent_id,
                            "brand": brand,
                            "domain": domain,
                            "url": result["url"],
                            "relevance_score": round(result["score"], 2),
                            "title": result.get("title", ""),
                            "search_query": result.get("search_query", ""),
                            "found": 1,
                        })
                    else:
                        results.append({
                            "intent_id": intent_id,
                            "brand": brand,
                            "domain": domain,
                            "url": "",
                            "relevance_score": 0.0,
                            "title": "",
                            "search_query": self.build_site_query(domain, self.extract_search_terms(intent)),
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
                        "error": str(e),
                    })
                
                # Rate limit: pause between requests
                if not use_api:
                    time.sleep(3)  # Be extra careful with scraping
            
            # Break outer loop if limit reached
            if limit and searches_performed >= limit:
                break
        
        # Write output
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["intent_id", "brand", "domain", "url", "relevance_score", "title", "search_query", "found"]
        
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for r in results:
                w.writerow(r)
        
        print(f"\nWrote {len(results)} URL mappings to {output_csv}")
        found_count = sum(1 for r in results if r.get("found"))
        print(f"Found URLs: {found_count}/{len(results)} ({100*found_count/len(results):.1f}%)")
        
        if limit and searches_performed >= limit:
            print(f"\n💡 Tip: To continue, increase --limit or run again (results append-safe)")
