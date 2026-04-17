# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import chromedriver_autoinstaller
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

chromedriver_autoinstaller.install()
opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])
opts.add_experimental_option("useAutomationExtension", False)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
opts.add_argument("user-agent=" + UA)
driver = webdriver.Chrome(options=opts)
driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": UA})
driver.get("https://www.flipkart.com/apple-iphone-15-black-128-gb/product-reviews/itmbf14ef54f645d?pid=MOBGTAGPAQNVFZZY")
time.sleep(6)

soup = BeautifulSoup(driver.page_source, "lxml")

# Get review cards: children of div.lQLKCP that have class fWi7J_  
container = soup.find("div", class_="lQLKCP")
if not container:
    print("ERROR: lQLKCP container not found!")
    driver.quit()
    exit()

cards = [c for c in container.children if getattr(c, 'name', None) == 'div' 
         and 'fWi7J_' in (c.get('class') or [])]
print(f"Review cards found: {len(cards)}")

# Analyze first real review card (skip first few which may be stats)
for i, card in enumerate(cards):
    txt = card.get_text(" ", strip=True)
    if len(txt) < 50:
        continue
    print(f"\n=== CARD {i} (len={len(txt)}) ===")
    print("FULL TEXT:", txt[:300].encode('ascii','replace').decode())
    print("\nINNER STRUCTURE:")
    # Print all leaf-level tags with class info
    for tag in card.find_all(True):
        children_count = len(list(tag.children))
        inner_txt = tag.get_text(strip=True).encode('ascii','replace').decode()
        if 0 < len(inner_txt) < 200:
            print(f"  <{tag.name}> cls={tag.get('class')} -> '{inner_txt[:100]}'")
    if i > 5:
        break

# Check for next button via JS
next_info = driver.execute_script("""
    let links = document.querySelectorAll('a');
    let results = [];
    for (let a of links) {
        let txt = (a.innerText || '').trim();
        if (txt.toLowerCase().includes('next') || txt === '>') {
            results.push({href: a.href, text: txt, cls: a.className});
        }
    }
    return results.slice(0, 5);
""")
print("\n--- NEXT LINKS ---")
for n in next_info:
    print(f"  href={n['href']} text='{n['text']}' cls={n['cls']}")

driver.quit()
