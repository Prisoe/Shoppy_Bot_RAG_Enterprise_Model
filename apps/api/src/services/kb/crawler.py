"""
Shopify Help Center crawler + generic URL fetcher.
Respects robots.txt, extracts clean text from HTML.
"""
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from src.config import get_settings

settings = get_settings()

SHOPIFY_HELP_SECTIONS = [
    "/en/manual",
    "/en/partners",
    "/en/api",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RAGBot/1.0; +https://example.com/bot)",
    "Accept": "text/html,application/xhtml+xml",
}


def extract_text_from_html(html: str, url: str = "") -> dict:
    """Returns { title, text, product_area }."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove nav/footer/scripts
    for tag in soup(["nav", "footer", "script", "style", "aside", "header"]):
        tag.decompose()

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)

    # Main content heuristic
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|article|main", re.I))
    text_source = main or soup.body or soup

    text = text_source.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Guess product area from URL path
    product_area = _guess_product_area(url)

    return {"title": title or url, "text": text, "product_area": product_area}


def _guess_product_area(url: str) -> str:
    path = urlparse(url).path.lower()
    mapping = {
        "payments": "payments",
        "shipping": "shipping",
        "orders": "orders",
        "products": "products",
        "apps": "apps",
        "themes": "themes",
        "analytics": "analytics",
        "marketing": "marketing",
        "customers": "customers",
        "inventory": "inventory",
    }
    for key, val in mapping.items():
        if key in path:
            return val
    return "general"


async def fetch_url(url: str) -> dict | None:
    """Fetch a single URL and return extracted content."""
    try:
        async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            return extract_text_from_html(resp.text, url)
    except Exception as e:
        print(f"[crawler] Failed to fetch {url}: {e}")
        return None


async def discover_shopify_urls(
    base_url: str = None,
    max_pages: int = None,
    sections: list[str] = None,
) -> list[str]:
    """
    Crawl Shopify Help Center sitemap to discover article URLs.
    Returns list of URLs to ingest.
    """
    base_url = base_url or settings.shopify_help_center_url
    max_pages = max_pages or settings.shopify_scrape_max_pages
    sections = sections or SHOPIFY_HELP_SECTIONS

    urls = []
    sitemap_url = f"{base_url}/sitemap.xml"

    try:
        async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(sitemap_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "xml")
                locs = soup.find_all("loc")
                for loc in locs:
                    url = loc.get_text(strip=True)
                    if any(sec in url for sec in sections):
                        urls.append(url)
                        if len(urls) >= max_pages:
                            break
    except Exception as e:
        print(f"[crawler] Sitemap discovery failed: {e}")
        # Fallback: known high-value Shopify help sections
        urls = [
            f"{base_url}/en/manual/orders",
            f"{base_url}/en/manual/payments",
            f"{base_url}/en/manual/shipping",
            f"{base_url}/en/manual/products",
            f"{base_url}/en/manual/customers",
        ]

    return urls[:max_pages]
