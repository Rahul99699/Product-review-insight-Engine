# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from scraper import scrape_reviews

print("Testing updated scraper...")
df, name = scrape_reviews(
    "https://www.flipkart.com/apple-iphone-15-black-128-gb/product-reviews/itmbf14ef54f645d?pid=MOBGTAGPAQNVFZZY",
    max_pages=2
)
print(f"\nProduct: {name}")
print(f"Reviews scraped: {len(df)}")
if len(df) > 0:
    print("\nSample reviews:")
    for _, row in df.head(3).iterrows():
        print(f"  Rating: {row['rating']} | Title: {row['title']}")
        print(f"  Body: {str(row['review'])[:100]}")
        print(f"  Name: {row['name']} | Date: {row['date']}")
        print()
else:
    print("ERROR: No reviews scraped!")
