# Playwright-based JSON-LD Extractor

## Requirements
- Python 3.8+
- Playwright

## Install Playwright and dependencies

```
pip install playwright
playwright install
```

## Usage

Prepare a text file with one URL per line, e.g. `urls.txt`:

```
https://www.example.com/product/123
https://www.example.com/product/456
```

Run the script:

```
python scripts/extract_jsonld_playwright.py urls.txt output.json
```

- The script will visit each URL, render the page with JavaScript, and extract all JSON-LD blocks.
- Results are saved as a JSON dictionary: `{url: [list of JSON-LD dicts]}`

## Notes
- Processing is sequential for reliability. For large batches, parallelization is possible but may require rate limiting and error handling.
- Playwright may require additional system dependencies (see Playwright docs for your OS).
