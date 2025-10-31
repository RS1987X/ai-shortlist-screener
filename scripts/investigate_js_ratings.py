#!/usr/bin/env python3
"""
Investigate JavaScript-based rating data on product pages.
This script loads pages with a headless browser and extracts rating information
from various common JavaScript patterns.
"""

import json
import re
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def extract_js_ratings(url: str) -> dict:
    """
    Extract rating data from JavaScript on a product page.
    Returns dict with: rating_value, rating_count, source (where found)
    """
    result = {
        "url": url,
        "domain": urlparse(url).netloc,
        "rating_value": None,
        "rating_count": None,
        "review_count": None,
        "source": None,
        "raw_data": None,
        "error": None
    }
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Load page with timeout
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)  # Wait for JS execution
            
            # Strategy 1: Check window.CURRENT_PAGE (Kjell pattern)
            current_page = page.evaluate("() => window.CURRENT_PAGE")
            if current_page and isinstance(current_page, dict):
                rating = current_page.get("rating")
                num_reviews = current_page.get("numberOfReviews")
                num_ratings = current_page.get("numberOfRatings")
                
                if rating is not None:
                    result["rating_value"] = rating
                    result["rating_count"] = num_ratings or num_reviews
                    result["review_count"] = num_reviews
                    result["source"] = "window.CURRENT_PAGE"
                    result["raw_data"] = {
                        "rating": rating,
                        "numberOfReviews": num_reviews,
                        "numberOfRatings": num_ratings
                    }
            
            # Strategy 2: Check common window properties
            if not result["rating_value"]:
                for prop in ["__NEXT_DATA__", "__INITIAL_STATE__", "dataLayer", "_INITIAL_DATA_"]:
                    data = page.evaluate(f"() => window.{prop}")
                    if data:
                        # Search for rating patterns in the data
                        data_str = json.dumps(data)
                        
                        # Look for rating patterns
                        rating_patterns = [
                            r'"rating[Vv]alue["\s:]+(\d+\.?\d*)',
                            r'"rating["\s:]+(\d+\.?\d*)',
                            r'"averageRating["\s:]+(\d+\.?\d*)',
                        ]
                        
                        count_patterns = [
                            r'"rating[Cc]ount["\s:]+(\d+)',
                            r'"review[Cc]ount["\s:]+(\d+)',
                            r'"numberOfReviews["\s:]+(\d+)',
                            r'"numberOfRatings["\s:]+(\d+)',
                        ]
                        
                        for pattern in rating_patterns:
                            match = re.search(pattern, data_str)
                            if match:
                                result["rating_value"] = float(match.group(1))
                                result["source"] = f"window.{prop}"
                                break
                        
                        for pattern in count_patterns:
                            match = re.search(pattern, data_str)
                            if match:
                                result["rating_count"] = int(match.group(1))
                                if not result["source"]:
                                    result["source"] = f"window.{prop}"
                                break
                        
                        if result["rating_value"]:
                            result["raw_data"] = prop
                            break

            # Strategy 2b: Parse embedded JSON scripts (e.g., Bygghemma Hypernova PageView)
            if not result["rating_value"]:
                try:
                    # Bygghemma pattern: <script type="application/json" data-hypernova-key="PageView"> <!--{...}--> </script>
                    script = page.query_selector('script[type="application/json"][data-hypernova-key="PageView"]')
                    if script:
                        text = script.text_content() or ""
                        # Remove HTML comment wrappers if present
                        text = text.strip()
                        if text.startswith("<!--") and text.endswith("-->"):
                            text = text[4:-3]
                        data = json.loads(text)
                        # Heuristic paths where rating may live
                        # currentPage.product.reviewSummary.{averageScore, numberOfReviews}
                        cur = data
                        for key in ["currentPage", "product", "reviewSummary"]:
                            if isinstance(cur, dict) and key in cur:
                                cur = cur[key]
                            else:
                                cur = None
                                break
                        if isinstance(cur, dict):
                            avg = cur.get("averageScore") or cur.get("avgScore") or cur.get("score")
                            cnt = cur.get("numberOfReviews") or cur.get("reviewCount") or cur.get("ratingCount")
                            if avg is not None:
                                result["rating_value"] = float(avg)
                                result["rating_count"] = int(cnt) if isinstance(cnt, (int, float, str)) and str(cnt).isdigit() else cnt
                                result["source"] = "script[data-hypernova-key=PageView]"
                except Exception:
                    pass
            
            # Strategy 3: Check meta tags (sometimes ratings are there)
            if not result["rating_value"]:
                meta_rating = page.query_selector('meta[itemprop="ratingValue"]')
                meta_count = page.query_selector('meta[itemprop="ratingCount"], meta[itemprop="reviewCount"]')
                
                if meta_rating:
                    content = meta_rating.get_attribute("content")
                    if content:
                        result["rating_value"] = float(content)
                        result["source"] = "meta[itemprop]"
                
                if meta_count:
                    content = meta_count.get_attribute("content")
                    if content:
                        result["rating_count"] = int(content)
                        if not result["source"]:
                            result["source"] = "meta[itemprop]"
            
            # Strategy 4: Check visible DOM elements with common patterns
            if not result["rating_value"]:
                # Look for common rating display patterns
                rating_selectors = [
                    '[data-rating]',
                    '[class*="rating"][class*="value"]',
                    '[class*="star-rating"]',
                    '.rating-value',
                    '.product-rating',
                ]
                
                for selector in rating_selectors:
                    elem = page.query_selector(selector)
                    if elem:
                        # Check data attributes
                        for attr in ['data-rating', 'data-value', 'data-rating-value']:
                            val = elem.get_attribute(attr)
                            if val:
                                try:
                                    result["rating_value"] = float(val)
                                    result["source"] = f"DOM: {selector}[{attr}]"
                                    break
                                except ValueError:
                                    pass
                        
                        # Check text content
                        if not result["rating_value"]:
                            text = elem.inner_text()
                            match = re.search(r'(\d+\.?\d*)\s*[/]?\s*5', text)
                            if match:
                                result["rating_value"] = float(match.group(1))
                                result["source"] = f"DOM: {selector} text"
                        
                        if result["rating_value"]:
                            break
            
            browser.close()
            
    except PlaywrightTimeout:
        result["error"] = "Page load timeout"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main():
    """Process URLs from the test file."""
    import sys
    
    urls_file = "/tmp/missing_ratings_urls.txt"
    
    with open(urls_file, "r") as f:
        urls = [line.strip() for line in f if line.strip()]
    
    print(f"Investigating {len(urls)} URLs for JavaScript-based ratings...\n")
    
    results = []
    for i, url in enumerate(urls[:8], 1):  # Process first 8
        print(f"[{i}/{min(8, len(urls))}] Processing: {url[:80]}...")
        result = extract_js_ratings(url)
        results.append(result)
        
        # Print summary
        if result["error"]:
            print(f"  ❌ Error: {result['error']}")
        elif result["rating_value"]:
            print(f"  ✅ Rating: {result['rating_value']} ({result['rating_count']} reviews) - Source: {result['source']}")
        else:
            print(f"  ⚠️  No rating found")
        print()
    
    # Save detailed results
    output_file = "/tmp/js_ratings_investigation.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Detailed results saved to: {output_file}")
    
    # Summary
    found = sum(1 for r in results if r["rating_value"])
    print(f"\n📊 Summary: Found ratings in {found}/{len(results)} pages")
    
    # Group by source
    sources = {}
    for r in results:
        if r["source"]:
            sources[r["source"]] = sources.get(r["source"], 0) + 1
    
    if sources:
        print("\n📍 Sources found:")
        for source, count in sorted(sources.items(), key=lambda x: -x[1]):
            print(f"  - {source}: {count}")


if __name__ == "__main__":
    main()
