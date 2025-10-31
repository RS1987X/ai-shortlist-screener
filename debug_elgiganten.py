#!/usr/bin/env python3
"""Debug script to test Elgiganten sitemap parsing."""

import httpx
import xml.etree.ElementTree as ET

sitemap_url = "https://www.elgiganten.se/sitemaps/OCSEELG.pdp-1.xml"

# Same headers as in sitemap_search.py
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

print(f"Fetching: {sitemap_url}")
print()

with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
    resp = client.get(sitemap_url)
    
    print(f"Status: {resp.status_code}")
    print(f"Headers:")
    for key, value in resp.headers.items():
        print(f"  {key}: {value}")
    print()
    
    content = resp.content
    print(f"Content length: {len(content)} bytes")
    print(f"Content type: {type(content)}")
    print(f"First 200 bytes (raw): {content[:200]}")
    print()
    print(f"First 200 chars (decoded): {content[:200].decode('utf-8', errors='replace')}")
    print()
    
    # Check for gzip magic bytes
    if len(content) >= 2:
        print(f"Magic bytes: {content[:2].hex()}")
        if content[:2] == b'\x1f\x8b':
            print("  -> This is gzipped content!")
        else:
            print("  -> Not gzipped")
    print()
    
    # Try to parse
    try:
        root = ET.fromstring(content)
        print("✅ XML parsing successful!")
        print(f"Root tag: {root.tag}")
    except Exception as e:
        print(f"❌ XML parsing failed: {e}")
        print()
        # Try to find problematic character
        try:
            decoded = content.decode('utf-8')
            print(f"Content decodes OK as UTF-8, length: {len(decoded)}")
        except Exception as e2:
            print(f"UTF-8 decoding failed: {e2}")
