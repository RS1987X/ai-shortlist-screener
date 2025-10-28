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
        Does NOT check actual page content (that's the audit's job).
        
        Args:
            url: Product page URL
            intent: Intent dict
            result: Search result dict with 'title', 'snippet'
        
        Returns:
            Relevance score 0-1
        """
        score = 0.0
        
        # Extract key terms from intent
        category = intent.get("category", "").lower()
        constraints = intent.get("constraints", "").lower()
        
        # Combine searchable text
        text = " ".join([
            url.lower(),
            result.get("title", "").lower(),
            result.get("snippet", "").lower(),
        ])
        
        # Score based on category match
        if category and category in text:
            score += 0.3
        
        # Score based on key specs present
        key_specs = re.findall(r'\d+[×x]\d+|\d+\s*(?:mm|cm|L|W|V|Hz|GB|mAh|bar)', constraints)
        if key_specs:
            matches = sum(1 for spec in key_specs if spec.lower() in text)
            score += 0.4 * (matches / len(key_specs))
        
        # Bonus for being a product page (not category/landing)
        product_indicators = ["/p/", "/product/", "/produkter/", "-p-"]
        if any(ind in url.lower() for ind in product_indicators):
            score += 0.3
        
        return min(score, 1.0)
    
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
            return best
        
        return None
    
    def discover_all(
        self,
        intents_csv: str,
        peers_csv: str,
        output_csv: str,
        use_api: bool = True,
    ) -> None:
        """
        Discover URLs for all intent × peer combinations.
        
        Args:
            intents_csv: Path to intents CSV
            peers_csv: Path to peers CSV
            output_csv: Output path for audit_urls.csv
            use_api: Use Google API if configured
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
        
        for intent in intents:
            intent_id = intent.get("intent_id")
            
            for peer in peers:
                count += 1
                brand = peer.get("brand")
                domain = peer.get("domain")
                
                print(f"[{count}/{total}] Searching {brand} for {intent_id}...")
                
                try:
                    result = self.discover_url(intent, domain, brand, use_api=use_api)
                    
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
