"""
Alphastreet scraper

Stage 1: Scrape links from index pages
Mode: Full Scan
1. Scan page 1 to get the links and max page number
2. Create max number of tasks
3. Run them in async with max concurrency
4. Save data after each run
5. Keep a progress tracker in sqlite

Mode: Incremental
1. Run scan from page 1 in sync
2. Keep going until a URL is already available in database

Stage 2: Scrape the transcripts
1. Async tasks of pending / failed links
2. Scrape the data and save them in disk
3. Update the progress tracker

Stage 3: Parse transcripts
1. Check the database for pending trancripts
2. Parse and save them in disk for downstream tasks.
"""


import re
from pathlib import Path

import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

RAW_LINKS_HTML_DIR = Path("data")/"raw"/"links"
RAW_LINKS_HTML_DIR.mkdir(parents=True, exist_ok=True)

RAW_TEXT_HTML_DIR = Path("data")/"raw"/"text"
RAW_TEXT_HTML_DIR.mkdir(parents=True, exist_ok=True)

view_port = {'width': 1920, 'height': 1080}
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'

base_url = "https://alphastreet.com/india/category/transcripts/"


def save_file(content: str, output_file: Path, mode: str = "w") -> None:
    with open(output_file, mode, encoding="utf-8") as fp:
        fp.write(content)

# def annotate_links(soup: BeautifulSoup) -> None:
#     for a in soup.find_all("a", href=True):
#         link_text = a.get_text(strip=True)
#         if link_text:
#             a.string = f"{link_text} [{a["href"]}]"

def extract_links(soup: BeautifulSoup):
    for article in soup.select("article.finance-card"):
        a = article.select_one("h2 a")
        title = a.get_text(strip=True) # type:ignore
        url = a["href"] # type:ignore
        date = article.select_one(".text-muted span").get_text(strip=True).lstrip("● ").strip() # type:ignore
        type_ = "transcript" if "Transcript" in title else "article"
        print(f"{title}, {url}, {date}, {type_}\n")

def parse_page(html: str, fname: str) -> None:
    html_output_file = RAW_LINKS_HTML_DIR/f"{fname}.html"
    save_file(html, html_output_file)

    soup = BeautifulSoup(html, "html.parser")
    extract_links(soup)
    max_page = find_max_pages_count(soup)
    print(f"Max Page: {max_page}")

def find_max_pages_count(soup: BeautifulSoup) -> int:
    max_value = -1
    for a in soup.find_all("a", href=True):
        match = re.search(r'/transcripts/page/(\d+)/', a["href"])   # type:ignore
        page_num = int(match.group(1)) if match else -1
        if page_num > max_value:
            max_value = page_num
    return max_value

async def async_scrape():
    async with async_playwright() as play:
        browser = await play.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=user_agent,
            viewport=view_port                   # type: ignore
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)

        await page.wait_for_timeout(2000)

        html = await page.content()
        parse_page(html, "page-0")

asyncio.run(async_scrape())

