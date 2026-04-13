"""Selenium scraper for myscheme.gov.in — farmer / agriculture search pages."""

import hashlib
import logging
import time
from datetime import datetime

from langchain_core.documents import Document
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

log = logging.getLogger(__name__)

MYSCHEME_URLS = [
    "https://www.myscheme.gov.in/search?tags=farmer",
    "https://www.myscheme.gov.in/search?tags=agriculture",
]

# React site — try multiple selectors if layout changes.
CARD_SELECTORS = [
    "div[class*='card']",
    "div[class*='Card']",
    "[class*='scheme-card']",
    "[class*='SchemeCard']",
    "article",
    "a[href*='/schemes/']",
]


def _build_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 KisanBot-Scraper/1.0"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def scrape_latest_schemes():
    """
    Open each URL, wait for JS (PDF: ~4s), collect card-like blocks as Documents.
    """
    raw_docs: list[Document] = []
    driver = None
    try:
        driver = _build_driver()
        for url in MYSCHEME_URLS:
            log.info("Loading %s", url)
            driver.get(url)
            time.sleep(4)
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)
            except Exception:
                pass

            seen_local: set[str] = set()
            for css in CARD_SELECTORS:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, css)
                except Exception:
                    continue
                for el in elements:
                    try:
                        text = (el.text or "").strip()
                    except Exception:
                        continue
                    if len(text) < 50:
                        continue
                    if text in seen_local:
                        continue
                    seen_local.add(text)
                    raw_docs.append(
                        Document(
                            page_content=text,
                            metadata={
                                "source": url,
                                "type": "scheme",
                                "updated": datetime.now().strftime("%Y-%m-%d"),
                            },
                        )
                    )

        # Dedupe across URLs (same card sometimes repeats)
        by_hash: dict[str, Document] = {}
        for d in raw_docs:
            h = hashlib.sha256(d.page_content.encode("utf-8", errors="ignore")).hexdigest()[:24]
            by_hash[h] = d
        out = list(by_hash.values())
        log.info("Scrape finished: %s unique documents", len(out))
        return out
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
