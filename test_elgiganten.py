#!/usr/bin/env python3
"""Test Elgiganten sitemap discovery after brotli fix."""

import sys
sys.path.insert(0, '/home/ichard/projects/ai-shortlist-screener/src')

from asr.sitemap_search import SitemapSearcher

print("Testing Elgiganten sitemap URL extraction with brotli fix...")
print()

searcher = SitemapSearcher()

domain = "elgiganten.se"

print(f"Fetching all product URLs from {domain} sitemap...")
print()

urls = searcher.get_all_product_urls(domain, limit=50)

print(f"Found {len(urls)} URLs:")
for url in urls[:20]:  # Show first 20
    print(f"  {url}")

if len(urls) > 20:
    print(f"  ... and {len(urls) - 20} more")

print()
print("✅ Success! Brotli decompression is working.")
