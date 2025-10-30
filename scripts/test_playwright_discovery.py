"""
Test Playwright-based URL discovery with a few sample queries.
"""

import sys
sys.path.insert(0, 'src')

from asr.site_search_playwright import SiteSearchPlaywrightDiscoverer

# Sample intent for testing
test_intent = {
    "intent_id": "test_001",
    "category": "usb-hub",
    "constraints": "USB-C, 4 ports, PD charging",
}

test_retailers = [
    ("elgiganten.se", "Elgiganten"),
    ("netonnet.se", "NetOnNet"),
    ("kjell.com", "Kjell & Company"),
]

def main():
    print("🚀 Testing Playwright URL Discovery\n")
    print(f"Intent: {test_intent['category']} - {test_intent['constraints']}\n")
    
    with SiteSearchPlaywrightDiscoverer() as discoverer:
        for domain, brand in test_retailers:
            print(f"\n{'='*60}")
            print(f"Testing: {brand} ({domain})")
            print('='*60)
            
            try:
                result = discoverer.discover_url(test_intent, domain, brand)
                
                if result:
                    print(f"✅ Found product!")
                    print(f"   URL: {result['url']}")
                    print(f"   Title: {result['title']}")
                    print(f"   Score: {result['score']:.2f}")
                    print(f"   Query: {result['search_query']}")
                else:
                    print(f"❌ No product found")
            
            except Exception as e:
                print(f"❌ Error: {e}")
    
    print(f"\n{'='*60}")
    print("✓ Test complete!")

if __name__ == "__main__":
    main()
