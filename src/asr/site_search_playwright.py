"""
Site-Search Discovery with Playwright - Find product URLs with JS rendering.

Uses Playwright to handle JavaScript-rendered search results and extract
products from both search results and category pages.
"""

import csv
import time
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin, quote_plus
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# Site-specific search URL patterns
SEARCH_PATTERNS = {
    "elgiganten.se": "https://www.elgiganten.se/search?SearchTerm={query}",
    "netonnet.se": "https://www.netonnet.se/art/sok?q={query}",
    "kjell.com": "https://www.kjell.com/se/sok?query={query}",
    "clasohlson.com": "https://www.clasohlson.com/se/search?q={query}",
    "jula.se": "https://www.jula.se/catalog?searchQuery={query}",
    "biltema.se": "https://www.biltema.se/sv-se/sok?searchQuery={query}",
    "byggmax.se": "https://www.byggmax.se/search?q={query}",
    "bygghemma.se": "https://www.bygghemma.se/sok/?q={query}",
    "hornbach.se": "https://www.hornbach.se/shop/search/{query}/",
    "dustin.se": "https://www.dustin.se/search?q={query}",
    "rusta.com": "https://www.rusta.com/sv-se/sok?q={query}",
}


class SiteSearchPlaywrightDiscoverer:
    """Discovers product URLs using Playwright for JS-rendered sites."""
    
    def __init__(self):
        """Initialize discoverer."""
        self.playwright = None
        self.browser = None
    
    def __enter__(self):
        """Context manager entry."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def build_search_query(self, intent: Dict) -> str:
        """
        Build simplified search query from intent.
        
        For site search, use broader queries that match retailer search behavior.
        Focus on product type + 1-2 key specs, not exact specifications.
        """
        import re
        
        prompt = intent.get("prompt", "")
        category = intent.get("category", "")
        
        # Extract product type from prompt (first 2-3 words, cleaned)
        prompt_clean = re.sub(r'\d+[×x]', '', prompt)  # Remove quantity prefixes
        prompt_clean = re.sub(r'under\s+\d+\s*kr.*', '', prompt_clean)  # Remove price
        prompt_clean = re.sub(r'\s+', ' ', prompt_clean).strip()
        
        # Take first 2-3 meaningful words
        swedish_stopwords = {'med', 'och', 'för', 'till', 'som', 'i', 'på', 'av', 'från', 'enl'}
        words = [w for w in prompt_clean.split()[:6] if w.lower() not in swedish_stopwords][:3]
        product_type = " ".join(words).strip()
        
        # For site search, keep it simple - just product type + maybe 1 key spec
        # Don't include exact specs that might not match retailer's terminology
        query = product_type
        
        # Add category as fallback if product type is too short
        if len(query) < 5 and category:
            query = category.replace('-', ' ')
        
        return query
    
    def get_search_url(self, domain: str, query: str) -> Optional[str]:
        """Get search URL for domain."""
        pattern = SEARCH_PATTERNS.get(domain)
        if pattern:
            return pattern.format(query=quote_plus(query))
        return None
    
    def extract_product_links_from_page(self, page, domain: str, max_links: int = 15) -> List[Dict]:
        """
        Extract product links from any page (search results or category page).
        
        Args:
            page: Playwright page object
            domain: Retailer domain
            max_links: Maximum number of links to extract
        
        Returns:
            List of dicts with 'url' and 'title'
        """
        product_links = []
        seen_urls = set()
        
        try:
            # Wait for content to load
            page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeout:
            pass  # Continue even if timeout
        
        # Find all links - prioritize those in main content area
        # Skip obvious navigation/footer links
        links = page.locator('a[href]').all()
        
        for link in links[:150]:  # Check more links but filter better
            try:
                href = link.get_attribute('href')
                if not href:
                    continue
                
                # Skip obvious non-product links early
                href_lower = href.lower()
                skip_patterns = [
                    'support.google.com', 'facebook.com', 'instagram.com', 'twitter.com',
                    'linkedin.com', 'youtube.com', '/om-oss', '/kontakt', '/hjalp',
                    '/kundservice', '/villkor', '/cookies', '/policy', '/gdpr',
                    '#', 'javascript:', 'mailto:', 'tel:', '/cart', '/kassa',
                    '/kundkorg', '/login', '/logga-in', '/account', '/konto'
                ]
                if any(pattern in href_lower for pattern in skip_patterns):
                    continue
                
                # Make absolute
                if href.startswith('/'):
                    href = urljoin(f"https://{domain}", href)
                elif not href.startswith('http'):
                    continue
                
                # Check if it's a product page using same logic as discover.py
                if self._is_product_page(href):
                    # Skip duplicates
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    
                    # Get title
                    try:
                        title = link.inner_text(timeout=100)
                        title = ' '.join(title.split())  # Normalize whitespace
                    except:
                        title = ""
                    
                    # Only add if we got a reasonable title (filter out icons/empty links)
                    if title and len(title) > 3:
                        product_links.append({
                            'url': href,
                            'title': title,
                        })
                    
                    if len(product_links) >= max_links:
                        break
            except:
                continue
        
        return product_links
    
    def _is_product_page(self, url: str) -> bool:
        """
        Check if URL is a product page (reuse logic from discover.py).
        
        Args:
            url: URL to check
        
        Returns:
            True if product page, False if category/other
        """
        url_lower = url.lower()
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        
        # Strong product indicators
        strong_indicators = [
            "/product/", "/produkt/", "/p/", "/art/", "/artikel/",
            "-p-", "/item/", "/pd/"
        ]
        has_strong_indicator = any(ind in url_lower for ind in strong_indicators)
        
        # Product ID pattern
        has_product_id = bool(re.search(r'[/-]\d{4,}/?$', path))
        
        # Product code pattern
        has_product_code = bool(re.search(r'[/-][a-z]{2,}[0-9]+-[a-z]\d+[a-z0-9]*/?$', path, re.IGNORECASE))
        
        # Category suffix patterns (reject these)
        path_segments = [s for s in path.split('/') if s]
        last_segment = path_segments[-1] if path_segments else ""
        
        category_suffix_patterns = [
            r'-\d+-tum', r'-storre$', r'-mindre$', r'-kategorier$', r'-kategori$'
        ]
        has_category_suffix = any(re.search(pattern, last_segment) for pattern in category_suffix_patterns)
        
        is_category_name_only = bool(last_segment and not re.search(r'\d', last_segment) and len(last_segment) > 3)
        is_shallow_category = len(path_segments) <= 3 and not has_product_id and not has_product_code
        
        # Decision
        is_product = has_strong_indicator and (has_product_id or has_product_code)
        is_likely_category = is_category_name_only or has_category_suffix or is_shallow_category
        
        if is_likely_category and not is_product:
            return False
        
        if not has_strong_indicator and not has_product_id and not has_product_code:
            return False
        
        return True
    
    def search_site(self, domain: str, query: str) -> List[Dict]:
        """
        Search a retailer's website using Playwright.
        
        Args:
            domain: Retailer domain
            query: Search query
        
        Returns:
            List of product URLs with titles
        """
        search_url = self.get_search_url(domain, query)
        if not search_url:
            print(f"  ⚠ No search pattern for {domain}")
            return []
        
        try:
            context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # Navigate to search
            page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            
            # Handle cookie consent popups (common patterns)
            cookie_buttons = [
                'button:has-text("Acceptera")',  # Swedish
                'button:has-text("Godkänn")',
                'button:has-text("Accept")',
                'button:has-text("OK")',
                '#onetrust-accept-btn-handler',  # OneTrust
                '.cookie-accept',
                '[data-testid="cookie-accept"]',
            ]
            
            for selector in cookie_buttons:
                try:
                    page.click(selector, timeout=2000)
                    print(f"  ✓ Accepted cookies")
                    page.wait_for_load_state("networkidle", timeout=3000)
                    break
                except:
                    pass  # Try next selector
            
            # Wait a bit more for JS to render products after cookie acceptance
            import time
            time.sleep(2)
            
            # Extract products from search results
            products = self.extract_product_links_from_page(page, domain, max_links=10)
            
            # If no products found but page loaded, might be a category page
            # Try to extract products anyway
            if not products:
                print(f"  ℹ No direct product links, trying category extraction...")
                products = self.extract_product_links_from_page(page, domain, max_links=15)
            
            context.close()
            return products
        
        except Exception as e:
            print(f"  Error: {e}")
            return []
    
    def score_result(self, url: str, title: str, intent: Dict) -> float:
        """Score how well result matches intent."""
        score = 0.0
        
        category = intent.get("category", "").lower()
        constraints = intent.get("constraints", "").lower()
        
        text = f"{url} {title}".lower()
        
        # Category match
        if category and category in text:
            score += 0.3
        
        # Spec matches
        key_specs = re.findall(r'\d+[×x]\d+|\d+\s*(?:mm|cm|L|W|V|Hz|GB|mAh|bar|K)', constraints, re.IGNORECASE)
        if key_specs:
            matches = sum(1 for spec in key_specs if spec.lower() in text)
            score += 0.4 * (matches / len(key_specs))
        
        # Product page bonus
        if any(ind in url.lower() for ind in ["/product/", "/p/", "/produkter/"]):
            score += 0.3
        
        return min(score, 1.0)
    
    def discover_url(self, intent: Dict, peer_domain: str, peer_brand: str) -> Optional[Dict]:
        """Discover best product URL using Playwright site search."""
        query = self.build_search_query(intent)
        results = self.search_site(peer_domain, query)
        
        if not results:
            return None
        
        # Score and rank
        scored = []
        for result in results:
            score = self.score_result(result['url'], result['title'], intent)
            scored.append({
                'url': result['url'],
                'title': result['title'],
                'score': score,
                'search_query': f"playwright_site_search:{peer_domain} {query}",
            })
        
        # Return best
        if scored:
            return max(scored, key=lambda x: x['score'])
        
        return None
    
    def discover_all(
        self,
        intents_csv: str,
        peers_csv: str,
        output_csv: str,
        limit: Optional[int] = None,
    ) -> None:
        """Discover URLs for all intent × peer combinations."""
        intents = []
        with open(intents_csv, encoding="utf-8") as f:
            intents = list(csv.DictReader(f))
        
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
                    print(f"\n⚠ Limit reached")
                    break
                
                brand = peer.get("brand")
                domain = peer.get("domain")
                
                print(f"[{count}/{total}] Playwright search: {brand} for {intent_id}...")
                
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
                        query = self.build_search_query(intent)
                        results.append({
                            "intent_id": intent_id,
                            "brand": brand,
                            "domain": domain,
                            "url": "",
                            "relevance_score": 0.0,
                            "title": "",
                            "search_query": f"playwright_site_search:{domain} {query}",
                            "found": 0,
                        })
                    
                    time.sleep(2)  # Be polite
                
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
        
        print(f"\nWrote {len(results)} URL mappings to {output_csv}")
        found = sum(1 for r in results if r.get("found"))
        print(f"Found: {found}/{len(results)} ({100*found/len(results):.1f}%)")
