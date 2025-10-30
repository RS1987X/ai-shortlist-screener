"""
Site-Search Discovery Module - Find product URLs using retailer's own search.

Uses each retailer's on-site search functionality instead of Google,
avoiding API costs and getting more accurate, live product matches.
"""

import csv
import time
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin, quote_plus
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential


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
    # Add more as needed
}


class SiteSearchDiscoverer:
    """Discovers product URLs using each retailer's on-site search."""
    
    def __init__(self):
        """Initialize site search discoverer."""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
        }
    
    def build_search_query(self, intent: Dict) -> str:
        """
        Build search query from intent (same as Google-based approach).
        
        Args:
            intent: Intent dict with 'prompt', 'constraints', 'category'
        
        Returns:
            Search query string
        """
        from .discover import URLDiscoverer
        discoverer = URLDiscoverer()
        return discoverer.extract_search_terms(intent)
    
    def get_search_url(self, domain: str, query: str) -> Optional[str]:
        """
        Get the search URL for a specific domain.
        
        Args:
            domain: Retailer domain (e.g., 'elgiganten.se')
            query: Search query
        
        Returns:
            Full search URL or None if pattern unknown
        """
        pattern = SEARCH_PATTERNS.get(domain)
        if pattern:
            return pattern.format(query=quote_plus(query))
        return None
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    def search_site(self, domain: str, query: str) -> List[Dict]:
        """
        Search a retailer's website using their search function.
        
        Args:
            domain: Retailer domain
            query: Search query
        
        Returns:
            List of product URLs found with titles
        """
        search_url = self.get_search_url(domain, query)
        if not search_url:
            print(f"  ⚠ No search pattern configured for {domain}")
            return []
        
        try:
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True) as client:
                resp = client.get(search_url)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Extract product links - common patterns
                product_links = []
                
                # Look for links with common product URL patterns
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    
                    # Make absolute URL
                    if href.startswith('/'):
                        href = urljoin(f"https://{domain}", href)
                    
                    # Filter for product pages (common patterns)
                    if any(pattern in href.lower() for pattern in ['/product/', '/p/', '/produkter/', '-p-']):
                        # Skip pagination, cart, etc.
                        if any(skip in href.lower() for skip in ['?page=', '/cart', '/kundvagn']):
                            continue
                        
                        title = link.get_text(strip=True)
                        if title and href not in [p['url'] for p in product_links]:
                            product_links.append({
                                'url': href,
                                'title': title,
                            })
                
                return product_links[:10]  # Top 10 results
        
        except Exception as e:
            print(f"  Error searching {domain}: {e}")
            return []
    
    def score_result(self, url: str, title: str, intent: Dict) -> float:
        """
        Score how well a result matches the intent (reuse from discover.py).
        
        Args:
            url: Product URL
            title: Product title
            intent: Intent dict
        
        Returns:
            Relevance score 0-1
        """
        score = 0.0
        
        # Extract key terms
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
    
    def discover_url(
        self,
        intent: Dict,
        peer_domain: str,
        peer_brand: str,
    ) -> Optional[Dict]:
        """
        Discover best product URL using site search.
        
        Args:
            intent: Intent dict
            peer_domain: Peer's domain
            peer_brand: Peer's brand name
        
        Returns:
            Dict with 'url', 'score', 'title', 'search_query' or None
        """
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
                'search_query': f"site_search:{peer_domain} {query}",
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
        """
        Discover URLs for all intent × peer combinations using site search.
        
        Args:
            intents_csv: Path to intents CSV
            peers_csv: Path to peers CSV
            output_csv: Output path
            limit: Maximum searches to perform
        """
        # Load data
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
                    print(f"\n⚠ Limit of {limit} searches reached.")
                    break
                
                brand = peer.get("brand")
                domain = peer.get("domain")
                
                print(f"[{count}/{total}] Searching {brand} site for {intent_id}...")
                
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
                            "search_query": f"site_search:{domain} {query}",
                            "found": 0,
                        })
                    
                    # Be polite: rate limit
                    time.sleep(1.5)
                
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
        print(f"Found URLs: {found}/{len(results)} ({100*found/len(results):.1f}%)")
