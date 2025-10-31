"""
Rating Monitor Module

Tracks product ratings and review counts over time to identify trends,
popularity signals, and review velocity.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse

from .parse import extract_json_ld
from .js_fallback import fetch_with_js_fallback

logger = logging.getLogger(__name__)


def extract_rating_info(url: str, use_js_fallback: bool = False) -> Dict:
    """
    Extract rating information from a product page.
    
    Returns:
        dict with keys: rating_value, rating_count, source (jsonld/fallback)
    """
    result = {
        'rating_value': None,
        'rating_count': None,
        'source': None
    }
    
    try:
        # First try server-side JSON-LD
        from .fetch import fetch_html
        html = fetch_html(url)
        
        if html:
            json_ld_list = extract_json_ld(html, url)
            
            # Look for rating in Product schema
            for item in json_ld_list:
                if item.get('@type') == 'Product':
                    agg_rating = item.get('aggregateRating', {})
                    if agg_rating:
                        result['rating_value'] = agg_rating.get('ratingValue')
                        result['rating_count'] = agg_rating.get('reviewCount') or agg_rating.get('ratingCount')
                        result['source'] = 'jsonld'
                        break
        
        # If no rating found and JS fallback enabled, try that
        if not result['rating_value'] and use_js_fallback:
            logger.info(f"No rating in server HTML, trying JS fallback for {url}")
            js_result = fetch_with_js_fallback(url)
            
            if js_result and js_result.get('rating_value'):
                result['rating_value'] = js_result['rating_value']
                result['rating_count'] = js_result.get('rating_count', 0)
                result['source'] = js_result.get('rating_source', 'js_fallback')
    
    except Exception as e:
        logger.error(f"Error extracting rating from {url}: {e}")
    
    return result


def monitor_ratings(
    input_csv: Path,
    output_csv: Path,
    domain_filter: Optional[str] = None,
    use_js_fallback: bool = False
) -> None:
    """
    Monitor ratings for products, appending timestamped records.
    
    Args:
        input_csv: Path to audit results CSV with product URLs
        output_csv: Path to output CSV (will append if exists)
        domain_filter: Optional domain to filter (e.g., "clasohlson.com")
        use_js_fallback: Whether to use JS fallback for rating extraction
    """
    timestamp = datetime.utcnow().isoformat()
    
    # Read input URLs
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        urls = [row for row in reader]
    
    # Filter by domain if specified
    if domain_filter:
        urls = [row for row in urls if domain_filter in row['url']]
        logger.info(f"Filtered to {len(urls)} URLs matching domain: {domain_filter}")
    
    # Check if output file exists to determine if we need headers
    file_exists = output_csv.exists()
    
    # Open output file for appending
    with open(output_csv, 'a', newline='', encoding='utf-8') as f:
        fieldnames = [
            'timestamp',
            'url',
            'domain',
            'product_id',
            'rating_value',
            'rating_count',
            'source',
            'has_rating_current',
            'has_rating_audit',
            'rating_value_audit',
            'rating_count_audit'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        # Write header if file is new
        if not file_exists:
            writer.writeheader()
        
        # Process each URL
        for i, row in enumerate(urls, 1):
            url = row['url']
            logger.info(f"[{i}/{len(urls)}] Checking {url}")
            
            # Extract domain and product ID
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            
            # Try to extract product ID from URL
            product_id = None
            if '/p/' in url:
                product_id = url.split('/p/')[-1].split('?')[0].split('#')[0]
            
            # Get current rating info
            rating_info = extract_rating_info(url, use_js_fallback=use_js_fallback)
            
            # Get audit baseline data
            has_rating_audit = row.get('has_rating') == '1'
            rating_value_audit = row.get('rating_value', '')
            rating_count_audit = row.get('rating_count', '')
            
            # Write record
            writer.writerow({
                'timestamp': timestamp,
                'url': url,
                'domain': domain,
                'product_id': product_id or '',
                'rating_value': rating_info['rating_value'] or '',
                'rating_count': rating_info['rating_count'] or '',
                'source': rating_info['source'] or '',
                'has_rating_current': 1 if rating_info['rating_value'] else 0,
                'has_rating_audit': 1 if has_rating_audit else 0,
                'rating_value_audit': rating_value_audit,
                'rating_count_audit': rating_count_audit
            })
            
            logger.info(f"  Rating: {rating_info['rating_value']} ({rating_info['rating_count']} reviews) via {rating_info['source']}")
    
    logger.info(f"✓ Rating monitoring complete. Results written to {output_csv}")


def analyze_rating_trends(monitor_csv: Path) -> Dict:
    """
    Analyze rating trends from monitoring data.
    
    Returns:
        Dictionary with trend analysis insights
    """
    with open(monitor_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        records = list(reader)
    
    if not records:
        return {'error': 'No records found'}
    
    # Group by product
    products = {}
    for record in records:
        url = record['url']
        if url not in products:
            products[url] = []
        products[url].append(record)
    
    # Analyze trends
    trends = {
        'total_products': len(products),
        'products_with_ratings': 0,
        'products_gaining_reviews': 0,
        'products_improving_ratings': 0,
        'top_review_gainers': []
    }
    
    for url, history in products.items():
        # Sort by timestamp
        history.sort(key=lambda x: x['timestamp'])
        
        if len(history) < 2:
            continue
        
        first = history[0]
        last = history[-1]
        
        # Check if product has ratings
        if last.get('rating_value'):
            trends['products_with_ratings'] += 1
        
        # Check for review count changes
        try:
            first_count = int(first.get('rating_count') or 0)
            last_count = int(last.get('rating_count') or 0)
            
            if last_count > first_count:
                trends['products_gaining_reviews'] += 1
                gain = last_count - first_count
                trends['top_review_gainers'].append({
                    'url': url,
                    'product_id': last.get('product_id'),
                    'gain': gain,
                    'from': first_count,
                    'to': last_count
                })
        except (ValueError, TypeError):
            pass
        
        # Check for rating improvements
        try:
            first_rating = float(first.get('rating_value') or 0)
            last_rating = float(last.get('rating_value') or 0)
            
            if last_rating > first_rating:
                trends['products_improving_ratings'] += 1
        except (ValueError, TypeError):
            pass
    
    # Sort top gainers
    trends['top_review_gainers'].sort(key=lambda x: x['gain'], reverse=True)
    trends['top_review_gainers'] = trends['top_review_gainers'][:10]  # Top 10
    
    return trends
