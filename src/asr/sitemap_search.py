"""
Sitemap-based URL Discovery - Search product sitemaps for matching products.

Uses retailer sitemaps (respects robots.txt) to find products without
needing search endpoints or JavaScript rendering.
"""

import csv
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
    "byggmax.se": "https://www.byggmax.se/pub/media/Sitemap_sv_se_category.xml",
    "clasohlson.com": "https://www.clasohlson.com/sitemap.xml",
    "distit.se": "https://distit.se/sv/wp-sitemap.xml",
    "elgiganten.se": "https://www.elgiganten.se/sitemaps/OCSEELG.pdp.index.sitemap.xml",
    "hornbach.se": "https://www.hornbach.se/sitemap/sitemap.xml",
    "jula.se": "https://www.jula.se/sitemap.1.xml",
    "k-bygg.se": "https://k-bygg.se/sitemap/index.xml",
    "kjell.com": "https://www.kjell.com/sitemap.xml",
    "mekonomen.se": "https://d3sjey3kqst1or.cloudfront.net/media/categories_cms_google_sitemap.xml",
    "rusta.com": "https://www.rusta.com/sitemap.xml",
    # Note: netonnet.se, dustin.se, alligo.com, beijerbygg.se don't have sitemaps in robots.txt
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
        self.client = httpx.Client(timeout=30.0)
    
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
    
    def extract_urls_from_sitemap(self, sitemap_url: str) -> List[str]:
        """
        Extract all product URLs from a sitemap.
        
        Args:
            sitemap_url: URL of the sitemap
        
        Returns:
            List of product URLs
        """
        try:
            resp = self.client.get(sitemap_url)
            resp.raise_for_status()
            
            root = ET.fromstring(resp.content)
            urls = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            
            return [url.text for url in urls if url.text]
        
        except Exception as e:
            print(f"  Error fetching sitemap {sitemap_url}: {e}")
            return []
    
    def get_all_product_urls(self, domain: str, limit: Optional[int] = None) -> List[str]:
        """
        Get all product URLs for a domain.
        
        Args:
            domain: Retailer domain
            limit: Maximum number of sitemaps to fetch (for testing)
        
        Returns:
            List of all product URLs
        """
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
        
        # Extract key terms from prompt (first few words)
        prompt_clean = re.sub(r'under\s+\d+\s*kr.*', '', prompt)  # Remove price
        prompt_clean = re.sub(r'\d+[×x]', '', prompt_clean)  # Remove quantities
        
        swedish_stopwords = {'med', 'och', 'för', 'till', 'som', 'i', 'på', 'av', 'från', 'enl'}
        words = [w for w in self.normalize_text(prompt_clean).split() if w not in swedish_stopwords][:4]
        
        # Extract specs from constraints
        specs = []
        
        # Numeric specs (20000mah, 4k, 100w, etc.) - normalize spaces in numbers
        # Handle "20 000 mAh" -> "20000mah" and keep decimals like "1.5L" intact
        constraints_normalized = re.sub(r'(\d+)\s+(\d+)', r'\1\2', constraints)  # Remove spaces in numbers
        numeric_specs = re.findall(r'\d+(?:\.\d+)?\s*(?:mah|k|w|hz|gb|l|mm|m|tum|bar|ghz)', constraints_normalized, re.IGNORECASE)
        specs.extend([self.normalize_text(s).replace(' ', '') for s in numeric_specs])  # Remove any remaining spaces
        
        # Standards (USB-C, HDMI, PD, etc.)
        standards = re.findall(r'\b(?:usb-c|usb|hdmi|pd|ip\d+|ax\d+|ips|hepa)\b', constraints, re.IGNORECASE)
        specs.extend([self.normalize_text(s) for s in standards])
        
        # Combine: product type + key words + specs
        terms = [product_type] + words + specs[:3]
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
        # Any term without digits is considered a non-numeric anchor (e.g., category, standards like usb-c/hdmi)
        non_numeric_terms = [t for t in search_terms if not re.search(r'\d+', t)]
        
        # Get all product URLs (limit to first 5 sitemaps for speed during development)
        all_urls = self.get_all_product_urls(domain, limit=5)
        
        if not all_urls:
            return []
        
        # Score each URL
        scored_results = []
        category_only_results = []  # Fallback: products matching category + descriptive terms
        
        for url in all_urls:
            score, details = self.score_url(url, search_terms)
            if score > 0:
                # Guardrail: require at least one non-numeric term match (to avoid numeric-only false positives
                # like lengths such as 32mm/30m matching unrelated products like pool hoses)
                has_non_numeric_match = any(t in details['matched_terms'] for t in non_numeric_terms)
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
