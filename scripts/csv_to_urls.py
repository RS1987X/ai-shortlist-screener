import csv
import sys

"""
Usage:
    python scripts/csv_to_urls.py data/test_discovery_small.csv urls.txt

Extracts the 'url' column from the input CSV and writes each URL to a new line in the output file.
"""

def csv_to_urls(input_csv, output_txt):
    with open(input_csv, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        with open(output_txt, 'w', encoding='utf-8') as outfile:
            for row in reader:
                url = row.get('url')
                if url:
                    outfile.write(url.strip() + '\n')

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/csv_to_urls.py <input.csv> <output.txt>")
        sys.exit(1)
    csv_to_urls(sys.argv[1], sys.argv[2])
