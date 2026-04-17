import time
import re
import pandas as pd
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


def get_driver():
    chromedriver_autoinstaller.install()
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("user-agent=" + UA)
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": UA})
    return driver


def get_reviews_url(product_url: str) -> str:
    """Convert a Flipkart product URL to its all-reviews URL."""
    if "flipkart.com" not in product_url:
        raise ValueError("URL must be a Flipkart product URL.")
    if "/p/" in product_url:
        reviews_url = product_url.replace("/p/", "/product-reviews/")
    else:
        reviews_url = product_url
    base = reviews_url.split("?")[0]
    pid = ""
    if "pid=" in product_url:
        for part in product_url.split("&"):
            if "pid=" in part:
                pid = part.split("pid=")[-1]
                break
    if pid:
        reviews_url = f"{base}?pid={pid}"
    else:
        reviews_url = base
    return reviews_url


def _clean(text: str) -> str:
    """Strip emoji and extra whitespace from text."""
    # Remove emoji/non-ASCII chars that cause Windows CP1252 issues
    text = text.encode("ascii", "replace").decode("ascii")
    text = re.sub(r"\?+", "", text)       # remove ? placeholders from emoji
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def scrape_page(soup) -> list:
    """
    Extract reviews from a BeautifulSoup page using Flipkart's current
    React-based DOM (as of 2025).

    Card structure (each card is a div.fWi7J_ inside div.lQLKCP):
      - Rating:  first div.css-146c3p1 whose text matches a decimal number
      - Title:   div.css-146c3p1 that is NOT the rating / emoji / "Review for:"
      - Body:    span.css-1jxf684
      - Name:    first div.css-146c3p1 inside the bottom info section
      - Date:    div with class r-dnmrzs (contains "Mon, YYYY")
    """
    reviews = []

    container = soup.find("div", class_="lQLKCP")
    if not container:
        # Fallback: try to find any fWi7J_ divs directly
        cards = soup.find_all("div", class_=lambda c: c and "fWi7J_" in c)
    else:
        cards = [
            c for c in container.children
            if getattr(c, "name", None) == "div"
            and "fWi7J_" in (c.get("class") or [])
        ]

    for card in cards:
        try:
            full_text = card.get_text(" ", strip=True)
            # Skip non-review cards (nav/filter bars, rating histogram, etc.)
            if len(full_text) < 50:
                continue
            if "User reviews sorted by" in full_text:
                continue
            if "ratings and" in full_text and "reviews" in full_text and "Helpful" not in full_text:
                continue

            # ── Review body ──────────────────────────────────────────────────
            body_span = card.find("span", class_="css-1jxf684")
            if not body_span:
                continue
            body = body_span.get_text(" ", strip=True)
            if len(body) < 5:
                continue

            # ── All css-146c3p1 divs in order ────────────────────────────────
            all_divs = card.find_all("div", class_=lambda c: c and "css-146c3p1" in c)

            rating = "N/A"
            title = ""
            name = "Anonymous"
            date = ""

            for div in all_divs:
                txt = div.get_text(strip=True)
                # Rating: decimal number like "4.0" or "5.0"
                if re.fullmatch(r"[1-5](\.\d)?", txt):
                    if rating == "N/A":
                        rating = txt
                    continue

            # Title: a short div that is not the rating, not emoji-only, not "Review for:"
            for div in all_divs:
                txt = div.get_text(strip=True)
                txt_clean = _clean(txt)
                if (
                    re.fullmatch(r"[1-5](\.\d)?", txt)
                    or not txt_clean
                    or txt_clean.startswith("Review for:")
                    or txt_clean.startswith("Verified")
                    or txt_clean.startswith("Helpful")
                    or txt_clean == body.strip()[:len(txt_clean)]
                    or len(txt_clean) > 120
                    or re.fullmatch(r"\W+", txt_clean)
                ):
                    continue
                # First short text that isn't any of the above → title
                if 2 < len(txt_clean) <= 80:
                    title = txt_clean
                    break

            # Date: div with r-dnmrzs class
            date_div = card.find("div", class_=lambda c: c and "r-dnmrzs" in c)
            if date_div:
                date = _clean(date_div.get_text(strip=True))

            # Name: look for "Name, City" pattern — it's a css-g5y9jx div containing
            # two css-146c3p1 children (first name, second ", City")
            name_candidates = card.find_all(
                "div", class_=lambda c: c and "css-g5y9jx" in c
            )
            for nc in name_candidates:
                children = [
                    ch for ch in nc.children
                    if getattr(ch, "name", None) == "div"
                ]
                if len(children) >= 2:
                    first = children[0].get_text(strip=True)
                    second = children[1].get_text(strip=True)
                    if (
                        second.startswith(",")
                        and 3 < len(first) < 60
                        and not any(kw in first for kw in ["Helpful", "Verified", "Review", "Purchase"])
                    ):
                        name = _clean(first)
                        break

            reviews.append({
                "name": name,
                "rating": rating,
                "title": title,
                "review": body,
                "date": date,
            })

        except Exception:
            continue

    return reviews


def scrape_reviews(product_url: str, max_pages: int = 15):
    """
    Scrape reviews from a Flipkart product URL.
    Returns (DataFrame, product_name).
    """
    reviews_url = get_reviews_url(product_url)
    driver = get_driver()
    all_reviews = []
    product_name = "Unknown Product"

    try:
        driver.get(reviews_url)
        time.sleep(4)

        # Product name from page title
        try:
            title_raw = driver.title
            product_name = re.sub(r"Reviews?:?.*", "", title_raw).strip().strip("|").strip()
            if not product_name:
                product_name = title_raw.split("|")[0].strip()
        except Exception:
            pass

        page = 1
        seen_texts = set()

        while page <= max_pages:
            soup = BeautifulSoup(driver.page_source, "lxml")
            page_reviews = scrape_page(soup)

            new_reviews = []
            for r in page_reviews:
                key = r["review"][:80]
                if key not in seen_texts:
                    seen_texts.add(key)
                    new_reviews.append(r)

            if not new_reviews:
                print(f"  Page {page}: no new reviews — stopping.")
                break

            all_reviews.extend(new_reviews)
            print(f"  Page {page}: +{len(new_reviews)} reviews (total: {len(all_reviews)})")

            # ── Navigate to next page ─────────────────────────────────────────
            navigated = False

            # Method 1: look for a clickable "Next" element
            try:
                next_el = driver.find_element(
                    By.XPATH,
                    "//*[normalize-space(text())='Next' or normalize-space(text())='>']"
                    "[ancestor::a or self::a or ancestor::button or self::button]"
                )
                driver.execute_script("arguments[0].click();", next_el)
                time.sleep(3)
                navigated = True
            except Exception:
                pass

            # Method 2: manipulate the URL page parameter
            if not navigated:
                try:
                    sep = "&" if "?" in reviews_url else "?"
                    next_url = f"{reviews_url}{sep}page={page + 1}"
                    driver.get(next_url)
                    time.sleep(3)
                    navigated = True
                except Exception:
                    pass

            if not navigated:
                break

            page += 1

    finally:
        driver.quit()

    if not all_reviews:
        return pd.DataFrame(), product_name

    df = pd.DataFrame(all_reviews)
    df.drop_duplicates(subset=["review"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df, product_name
