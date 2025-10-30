
import asyncio
import json
import sys
from pathlib import Path
from typing import List
from playwright.async_api import async_playwright

def extract_urls(input_file: str) -> List[str]:
    """
    Extract URLs from a plain text file (one per line) or a CSV file (with 'url' column).
    """
    if input_file.endswith('.csv'):
        import csv
        with open(input_file, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            return [row['url'].strip() for row in reader if 'url' in row and row['url'].strip()]
    else:
        return [line.strip() for line in Path(input_file).read_text().splitlines() if line.strip()]

async def extract_jsonld_from_url(url: str) -> List[dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        await page.wait_for_load_state('networkidle')
        jsonld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
        jsonld_data = []
        for script in jsonld_scripts:
            content = await script.inner_text()
            try:
                data = json.loads(content)
                jsonld_data.append(data)
            except Exception:
                pass  # skip invalid JSON
        await browser.close()
        return jsonld_data

async def process_urls(input_file: str, output_file: str):
    urls = extract_urls(input_file)
    results = {}
    for url in urls:
        print(f"Processing: {url}")
        try:
            jsonld = await extract_jsonld_from_url(url)
            results[url] = jsonld
        except Exception as e:
            print(f"Error processing {url}: {e}")
            results[url] = None
    Path(output_file).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Done. Results saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/extract_jsonld_playwright.py <input_urls.txt|input.csv> <output.json>")
        sys.exit(1)
    asyncio.run(process_urls(sys.argv[1], sys.argv[2]))
