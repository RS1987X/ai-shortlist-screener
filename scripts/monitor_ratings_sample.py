#!/usr/bin/env python3
"""
Quick Rating Monitor - Sample products from sitemap and track ratings

This script:
1. Fetches sitemap from Clas Ohlson
2. Samples N product URLs randomly
3. Extracts current ratings and review counts
4. Saves timestamped results for trend analysis
"""

import csv
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.asr.fetch import fetch_html
from src.asr.parse import extract_jsonld

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
# Ensure logging flushes immediately
for handler in logging.root.handlers:
    handler.flush = lambda: sys.stdout.flush()

logger = logging.getLogger(__name__)


def fetch_sitemap_urls(sitemap_url: str, max_urls: int = 10000) -> List[str]:
    """
    Fetch product URLs from sitemap.
    
    Args:
        sitemap_url: URL to the sitemap XML
        max_urls: Maximum number of URLs to fetch
        
    Returns:
        List of product URLs
    """
    logger.info(f"Fetching sitemap: {sitemap_url}")
    
    try:
        html = fetch_html(sitemap_url)
        if not html:
            logger.error("Failed to fetch sitemap")
            return []
        
        # Parse XML
        root = ET.fromstring(html)
        
        # Handle XML namespace
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Extract URLs
        urls = []
        for url_elem in root.findall('.//ns:url', ns):
            loc = url_elem.find('ns:loc', ns)
            if loc is not None and loc.text:
                urls.append(loc.text)
                if len(urls) >= max_urls:
                    break
        
        logger.info(f"Found {len(urls)} URLs in sitemap")
        return urls
    
    except Exception as e:
        logger.error(f"Error parsing sitemap: {e}")
        return []


def extract_rating_from_url(url: str) -> Dict[str, Optional[str]]:
    """
    Extract rating and price information from a product URL.
    
    Returns:
        dict with: rating_value, rating_count, price, currency, availability, source, error
    """
    result = {
        'rating_value': None,
        'rating_count': None,
        'price': None,
        'currency': None,
        'availability': None,
        'source': None,
        'error': None
    }
    
    try:
        html = fetch_html(url)
        if not html:
            result['error'] = 'fetch_failed'
            return result
        
        # Extract JSON-LD
        json_ld_list = extract_jsonld(html, url)
        
        # Look for rating and price in Product schema
        for item in json_ld_list:
            if item.get('@type') == 'Product':
                # Extract rating
                agg_rating = item.get('aggregateRating', {})
                if agg_rating:
                    result['rating_value'] = agg_rating.get('ratingValue')
                    result['rating_count'] = (
                        agg_rating.get('reviewCount') or 
                        agg_rating.get('ratingCount')
                    )
                    result['source'] = 'jsonld'
                
                # Extract price from offers
                offers = item.get('offers')
                if offers:
                    # Offers can be a dict or a list
                    offer_list = offers if isinstance(offers, list) else [offers]
                    
                    for offer in offer_list:
                        if isinstance(offer, dict):
                            # Get price
                            price_val = offer.get('price')
                            if price_val:
                                result['price'] = str(price_val)
                                result['currency'] = offer.get('priceCurrency', '')
                                result['availability'] = offer.get('availability', '').split('/')[-1]
                                break
                
                # Once we find a Product with data, we're done
                if result['rating_value'] or result['price']:
                    break
    
    except Exception as e:
        result['error'] = str(e)
        logger.debug(f"Error extracting data from {url}: {e}")
    
    return result


def sample_and_monitor(
    domain: str = "clasohlson.com",
    sample_size: int = 1000,
    output_csv: Path = Path("data/rating_monitor.csv"),
    save_individual: bool = True
) -> None:
    """
    Sample products from sitemap and monitor their ratings.
    
    Uses hybrid approach:
    - Saves individual timestamped file in data/rating_monitor/ folder
    - Also appends to master file for easy trend analysis
    
    Args:
        domain: Domain to monitor (default: clasohlson.com)
        sample_size: Number of products to sample
        output_csv: Path to master output CSV file
        save_individual: Whether to save individual timestamped file (default: True)
    """
    timestamp = datetime.utcnow().isoformat()
    
    # Construct sitemap URL for Clas Ohlson
    # Try common sitemap patterns
    sitemap_urls = [
        f"https://www.{domain}/sitemap/sitemap_product_se.xml",  # Clas Ohlson specific
        f"https://www.{domain}/sitemap-products.xml",
        f"https://www.{domain}/sitemap_products.xml",
        f"https://www.{domain}/product-sitemap.xml",
        f"https://www.{domain}/sitemap.xml",
    ]
    
    all_urls = []
    for sitemap_url in sitemap_urls:
        logger.info(f"Trying sitemap: {sitemap_url}")
        urls = fetch_sitemap_urls(sitemap_url, max_urls=50000)
        if urls:
            all_urls = urls
            logger.info(f"✓ Found {len(urls)} products in sitemap")
            break
    
    if not all_urls:
        logger.error("Could not find sitemap with products")
        return
    
    # Filter for product pages (if needed)
    product_urls = [url for url in all_urls if '/p/' in url or '/product/' in url]
    logger.info(f"Filtered to {len(product_urls)} product URLs")
    
    # Sample random products
    if len(product_urls) > sample_size:
        sampled_urls = random.sample(product_urls, sample_size)
        logger.info(f"Sampled {sample_size} random products")
    else:
        sampled_urls = product_urls
        logger.info(f"Using all {len(sampled_urls)} products (less than sample size)")
    
    # Ensure output directory exists
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    # Prepare file paths for hybrid approach
    master_file = output_csv
    individual_file = None
    
    if save_individual:
        # Create individual file with timestamp: data/rating_monitor/20251031_163751.csv
        monitor_dir = output_csv.parent / "rating_monitor"
        monitor_dir.mkdir(parents=True, exist_ok=True)
        
        # Format timestamp for filename: YYYYMMDD_HHMMSS
        timestamp_str = timestamp.replace(':', '').replace('-', '').replace('.', '')[:15]
        individual_file = monitor_dir / f"{timestamp_str}.csv"
    
    # Determine which files to write to
    files_to_write = []
    if individual_file:
        files_to_write.append(('individual', individual_file))
    files_to_write.append(('master', master_file))
    
    # Check if master file exists to determine if we need headers
    master_exists = master_file.exists()
    
    # Collect all records first
    all_records = []
    
    # Track timing for progress estimates
    import time
    start_time = time.time()
    
    # Process each URL
    for i, url in enumerate(sampled_urls, 1):
        if i % 50 == 0 or i == len(sampled_urls):
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (len(sampled_urls) - i) / rate if rate > 0 else 0
            
            progress_msg = (
                f"Progress: {i}/{len(sampled_urls)} ({i*100//len(sampled_urls)}%) | "
                f"Rate: {rate:.1f} products/sec | "
                f"ETA: {remaining/60:.1f} min"
            )
            logger.info(progress_msg)
            sys.stdout.flush()  # Flush buffer to show progress immediately
        
        # Extract domain and product ID
        parsed = urlparse(url)
        domain_clean = parsed.netloc.replace('www.', '')
        
        # Extract product ID from URL
        product_id = None
        if '/p/' in url:
            product_id = url.split('/p/')[-1].split('?')[0].split('#')[0]
        elif '/product/' in url:
            product_id = url.split('/product/')[-1].split('?')[0].split('#')[0]
        
        # Get rating info
        rating_info = extract_rating_from_url(url)
        
        # Prepare record
        record = {
            'timestamp': timestamp,
            'url': url,
            'domain': domain_clean,
            'product_id': product_id or '',
            'rating_value': rating_info['rating_value'] or '',
            'rating_count': rating_info['rating_count'] or '',
            'price': rating_info['price'] or '',
            'currency': rating_info['currency'] or '',
            'availability': rating_info['availability'] or '',
            'source': rating_info['source'] or '',
            'error': rating_info['error'] or ''
        }
        all_records.append(record)
        
        # Log interesting findings
        if rating_info['rating_value'] or rating_info['price']:
            logger.debug(
                f"  ✓ Product {product_id}: "
                f"Rating {rating_info['rating_value']} ({rating_info['rating_count']} reviews) | "
                f"Price {rating_info['price']} {rating_info['currency']}"
            )
    
    # Write to all target files
    fieldnames = [
        'timestamp',
        'url',
        'domain',
        'product_id',
        'rating_value',
        'rating_count',
        'price',
        'currency',
        'availability',
        'source',
        'error'
    ]
    
    for file_type, file_path in files_to_write:
        # Individual files always get headers, master only if new
        write_header = (file_type == 'individual') or (file_type == 'master' and not master_exists)
        
        # Individual files are always new, master appends
        mode = 'w' if file_type == 'individual' else 'a'
        
        with open(file_path, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if write_header:
                writer.writeheader()
            
            writer.writerows(all_records)
        
        if file_type == 'individual':
            logger.info(f"Saved individual run to: {file_path}")
        else:
            logger.info(f"Appended to master file: {file_path}")
    
    logger.info(f"✓ Rating monitoring complete!")
    if individual_file:
        logger.info(f"  Individual run: {individual_file}")
    logger.info(f"  Master file: {master_file}")
    logger.info(f"  Total products checked: {len(sampled_urls)}")
    
    # Print summary statistics
    print_summary(master_file, timestamp)


def print_summary(csv_path: Path, timestamp: str) -> None:
    """Print summary statistics for the monitoring run."""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        records = [r for r in reader if r['timestamp'] == timestamp]
    
    if not records:
        return
    
    total = len(records)
    with_ratings = sum(1 for r in records if r['rating_value'])
    with_reviews = sum(1 for r in records if r['rating_count'] and int(r['rating_count'] or 0) > 0)
    with_prices = sum(1 for r in records if r.get('price') and r['price'].strip())
    
    avg_rating = None
    avg_review_count = None
    avg_price = None
    currency_counts = {}
    
    if with_ratings:
        ratings = [float(r['rating_value']) for r in records if r['rating_value']]
        avg_rating = sum(ratings) / len(ratings) if ratings else None
    
    if with_reviews:
        counts = [int(r['rating_count']) for r in records if r['rating_count'] and r['rating_count'].isdigit()]
        avg_review_count = sum(counts) / len(counts) if counts else None
    
    if with_prices:
        prices = []
        for r in records:
            if r.get('price'):
                try:
                    prices.append(float(r['price']))
                    curr = r.get('currency', '')
                    currency_counts[curr] = currency_counts.get(curr, 0) + 1
                except ValueError:
                    pass
        avg_price = sum(prices) / len(prices) if prices else None
        main_currency = max(currency_counts.items(), key=lambda x: x[1])[0] if currency_counts else ''
    
    # Availability statistics
    availability_counts = {}
    for r in records:
        avail = r.get('availability', '').strip()
        if avail:
            availability_counts[avail] = availability_counts.get(avail, 0) + 1
    
    print("\n" + "="*60)
    print("RATING & PRICE MONITOR SUMMARY")
    print("="*60)
    print(f"Total products sampled:    {total}")
    print(f"Products with ratings:     {with_ratings} ({with_ratings*100//total}%)")
    print(f"Products with reviews:     {with_reviews} ({with_reviews*100//total}%)")
    print(f"Products with prices:      {with_prices} ({with_prices*100//total}%)")
    if avg_rating:
        print(f"Average rating:            {avg_rating:.2f}")
    if avg_review_count:
        print(f"Average review count:      {avg_review_count:.1f}")
    if avg_price and with_prices:
        print(f"Average price:             {avg_price:.2f} {main_currency}")
    if availability_counts:
        print(f"\nStock availability:")
        for status, count in sorted(availability_counts.items(), key=lambda x: -x[1]):
            print(f"  {status:20s} {count:5d} ({count*100//total}%)")
    print("="*60)
    print(f"\nData saved to: {csv_path}")
    print(f"Timestamp: {timestamp}")
    print("\nTo analyze trends over time, run this script again later.")
    print("="*60 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Monitor product ratings from sitemap sample"
    )
    parser.add_argument(
        "--domain",
        default="clasohlson.com",
        help="Domain to monitor (default: clasohlson.com)"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=1000,
        help="Number of products to sample (default: 1000)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/rating_monitor.csv"),
        help="Output CSV file (default: data/rating_monitor.csv)"
    )
    
    args = parser.parse_args()
    
    sample_and_monitor(
        domain=args.domain,
        sample_size=args.sample_size,
        output_csv=args.out
    )
