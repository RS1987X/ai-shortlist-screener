#!/usr/bin/env python3
"""
Analyze Rating Trends - Identify products accelerating in reviews and ratings

This script analyzes rating_monitor.csv to find:
- Products gaining reviews fastest (reviews per day)
- Products with improving ratings
- Emerging products (started with few reviews, growing fast)
"""

import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def analyze_trends(monitor_csv: Path, output_trends: Path = None) -> Dict:
    """
    Analyze rating trends to identify accelerating products.
    
    Args:
        monitor_csv: Path to rating monitor CSV
        output_trends: Optional path to save detailed trends CSV
    
    Returns:
        Dictionary with trend analysis insights
    """
    with open(monitor_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        records = list(reader)
    
    if not records:
        print("❌ No records found in CSV")
        return {'error': 'No records found'}
    
    # Group by product
    products = {}
    for record in records:
        url = record['url']
        if url not in products:
            products[url] = []
        products[url].append(record)
    
    # Get unique timestamps
    timestamps = sorted(set(r['timestamp'] for r in records))
    
    if len(timestamps) < 2:
        print(f"⚠️  Need at least 2 monitoring runs to analyze trends")
        print(f"   Current runs: {len(timestamps)}")
        print(f"   Run the monitor script again to collect more data points.")
        return {'error': 'Need at least 2 monitoring runs', 'timestamps': len(timestamps)}
    
    # Analyze trends
    trends = {
        'total_products': len(products),
        'monitoring_runs': len(timestamps),
        'first_run': timestamps[0],
        'last_run': timestamps[-1],
        'products_with_ratings': 0,
        'products_gaining_reviews': 0,
        'products_improving_ratings': 0,
        'top_review_accelerators': [],  # Products gaining reviews fastest
        'top_rating_improvers': [],     # Products improving rating most
        'emerging_products': [],         # New products with growing reviews
        'hot_products': []               # High rating + fast review growth
    }
    
    detailed_trends = []
    
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
        
        # Calculate review acceleration
        try:
            first_count = int(first.get('rating_count') or 0)
            last_count = int(last.get('rating_count') or 0)
            first_rating = float(first.get('rating_value') or 0)
            last_rating = float(last.get('rating_value') or 0)
            
            # Calculate time difference in days
            first_time = datetime.fromisoformat(first['timestamp'])
            last_time = datetime.fromisoformat(last['timestamp'])
            time_diff_days = (last_time - first_time).total_seconds() / 86400
            
            if time_diff_days <= 0:
                continue
            
            review_gain = last_count - first_count
            rating_change = last_rating - first_rating
            
            if review_gain > 0:
                trends['products_gaining_reviews'] += 1
                reviews_per_day = review_gain / time_diff_days
                
                product_data = {
                    'url': url,
                    'product_id': last.get('product_id'),
                    'review_gain': review_gain,
                    'from_count': first_count,
                    'to_count': last_count,
                    'days': round(time_diff_days, 2),
                    'reviews_per_day': round(reviews_per_day, 2),
                    'current_rating': last_rating,
                    'first_rating': first_rating,
                    'rating_change': round(rating_change, 2),
                    'acceleration_score': round(reviews_per_day * (last_rating or 1), 2)
                }
                
                trends['top_review_accelerators'].append(product_data)
                detailed_trends.append(product_data)
                
                # Flag emerging products (started with few reviews, growing fast)
                if first_count < 10 and reviews_per_day > 0.5:
                    trends['emerging_products'].append(product_data)
                
                # Flag hot products (high rating + fast growth)
                if last_rating >= 4.0 and reviews_per_day > 1.0:
                    trends['hot_products'].append(product_data)
            
            # Check for rating improvements
            if rating_change > 0 and first_rating > 0:
                trends['products_improving_ratings'] += 1
                
                trends['top_rating_improvers'].append({
                    'url': url,
                    'product_id': last.get('product_id'),
                    'rating_change': round(rating_change, 2),
                    'from_rating': first_rating,
                    'to_rating': last_rating,
                    'review_count': last_count,
                    'reviews_per_day': round(review_gain / time_diff_days, 2) if review_gain > 0 else 0
                })
        
        except (ValueError, TypeError, KeyError) as e:
            continue
    
    # Sort and limit lists
    trends['top_review_accelerators'].sort(key=lambda x: x['reviews_per_day'], reverse=True)
    trends['top_review_accelerators'] = trends['top_review_accelerators'][:20]
    
    trends['top_rating_improvers'].sort(key=lambda x: x['rating_change'], reverse=True)
    trends['top_rating_improvers'] = trends['top_rating_improvers'][:20]
    
    trends['emerging_products'].sort(key=lambda x: x['reviews_per_day'], reverse=True)
    trends['emerging_products'] = trends['emerging_products'][:15]
    
    trends['hot_products'].sort(key=lambda x: x['acceleration_score'], reverse=True)
    trends['hot_products'] = trends['hot_products'][:15]
    
    # Save detailed trends if requested
    if output_trends and detailed_trends:
        with open(output_trends, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'product_id', 'url', 'review_gain', 'from_count', 'to_count',
                'days', 'reviews_per_day', 'current_rating', 'first_rating',
                'rating_change', 'acceleration_score'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Sort by reviews per day
            detailed_trends.sort(key=lambda x: x.get('reviews_per_day', 0), reverse=True)
            writer.writerows(detailed_trends)
        
        print(f"✓ Detailed trends saved to: {output_trends}")
    
    return trends


def print_analysis(trends: Dict) -> None:
    """Print formatted trend analysis."""
    
    if 'error' in trends:
        return
    
    # Calculate time span
    try:
        first = datetime.fromisoformat(trends['first_run'])
        last = datetime.fromisoformat(trends['last_run'])
        days = (last - first).total_seconds() / 86400
    except:
        days = 0
    
    print("\n" + "="*80)
    print("🚀 RATING ACCELERATION ANALYSIS")
    print("="*80)
    print(f"\n📊 Overview:")
    print(f"   Total products tracked:     {trends['total_products']}")
    print(f"   Monitoring runs:            {trends['monitoring_runs']}")
    print(f"   Time span:                  {days:.1f} days")
    print(f"   Products with ratings:      {trends['products_with_ratings']}")
    print(f"   Products gaining reviews:   {trends['products_gaining_reviews']}")
    print(f"   Products improving ratings: {trends['products_improving_ratings']}")
    
    # Top Review Accelerators
    if trends['top_review_accelerators']:
        print(f"\n🔥 TOP REVIEW ACCELERATORS (Reviews per Day)")
        print("="*80)
        for i, p in enumerate(trends['top_review_accelerators'][:10], 1):
            print(f"\n{i}. Product: {p['product_id']}")
            print(f"   Reviews per day: {p['reviews_per_day']:.2f}")
            print(f"   Growth: {p['from_count']} → {p['to_count']} (+{p['review_gain']}) in {p['days']:.1f} days")
            print(f"   Current rating: {p['current_rating']}")
            print(f"   URL: {p['url'][:70]}...")
    
    # Emerging Products
    if trends['emerging_products']:
        print(f"\n🌟 EMERGING PRODUCTS (New & Growing Fast)")
        print("="*80)
        for i, p in enumerate(trends['emerging_products'][:10], 1):
            print(f"\n{i}. Product: {p['product_id']}")
            print(f"   Reviews per day: {p['reviews_per_day']:.2f}")
            print(f"   Started with: {p['from_count']} reviews, now: {p['to_count']}")
            print(f"   Current rating: {p['current_rating']}")
            print(f"   URL: {p['url'][:70]}...")
    
    # Hot Products
    if trends['hot_products']:
        print(f"\n⭐ HOT PRODUCTS (High Rating + Fast Growth)")
        print("="*80)
        for i, p in enumerate(trends['hot_products'][:10], 1):
            print(f"\n{i}. Product: {p['product_id']}")
            print(f"   Rating: {p['current_rating']} ⭐")
            print(f"   Reviews per day: {p['reviews_per_day']:.2f}")
            print(f"   Total reviews: {p['to_count']}")
            print(f"   Acceleration score: {p['acceleration_score']}")
            print(f"   URL: {p['url'][:70]}...")
    
    # Top Rating Improvers
    if trends['top_rating_improvers']:
        print(f"\n📈 TOP RATING IMPROVERS")
        print("="*80)
        for i, p in enumerate(trends['top_rating_improvers'][:10], 1):
            print(f"\n{i}. Product: {p['product_id']}")
            print(f"   Rating change: {p['from_rating']:.1f} → {p['to_rating']:.1f} (+{p['rating_change']:.2f})")
            print(f"   Reviews: {p['review_count']}")
            print(f"   URL: {p['url'][:70]}...")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze rating trends to find accelerating products"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/rating_monitor.csv"),
        help="Input rating monitor CSV (default: data/rating_monitor.csv)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/rating_trends.csv"),
        help="Output trends CSV (default: data/rating_trends.csv)"
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"❌ File not found: {args.input}")
        print(f"\nRun the rating monitor first:")
        print(f"  .venv/bin/python scripts/monitor_ratings_sample.py --sample-size 1000")
        sys.exit(1)
    
    trends = analyze_trends(args.input, args.out)
    print_analysis(trends)
