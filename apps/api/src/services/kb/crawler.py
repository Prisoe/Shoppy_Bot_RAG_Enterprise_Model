"""
KB crawler — fetches Shopify help articles with browser headers.
Falls back to curated static URL list if Shopify blocks requests.
"""
import httpx
import re
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from src.config import get_settings

settings = get_settings()

# Browser-like headers to avoid 403s
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

# Curated Shopify help URLs — used as fallback if live fetch fails
SHOPIFY_CURATED_URLS = [
    "https://help.shopify.com/en/manual/orders/refunds",
    "https://help.shopify.com/en/manual/orders",
    "https://help.shopify.com/en/manual/orders/fulfillment",
    "https://help.shopify.com/en/manual/payments/shopify-payments",
    "https://help.shopify.com/en/manual/payments/shopify-payments/supported-countries",
    "https://help.shopify.com/en/manual/payments/shopify-payments/fraud-prevention",
    "https://help.shopify.com/en/manual/shipping",
    "https://help.shopify.com/en/manual/shipping/setting-up-and-managing-your-shipping",
    "https://help.shopify.com/en/manual/shipping/shopify-shipping",
    "https://help.shopify.com/en/manual/products",
    "https://help.shopify.com/en/manual/products/inventory",
    "https://help.shopify.com/en/manual/products/variants",
    "https://help.shopify.com/en/manual/customers",
    "https://help.shopify.com/en/manual/customers/manage-customers",
    "https://help.shopify.com/en/manual/discounts",
    "https://help.shopify.com/en/manual/promoting-marketing/discount-codes",
    "https://help.shopify.com/en/manual/reports-and-analytics",
    "https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports",
    "https://help.shopify.com/en/manual/your-account/billing",
    "https://help.shopify.com/en/manual/taxes",
    "https://help.shopify.com/en/manual/apps",
    "https://help.shopify.com/en/manual/online-store/themes",
    "https://help.shopify.com/en/manual/domains",
    "https://help.shopify.com/en/manual/sell-in-person/shopify-pos",
    "https://help.shopify.com/en/manual/checkout-settings",
    "https://help.shopify.com/en/manual/online-store/storefront-password",
    "https://help.shopify.com/en/manual/your-account",
    "https://help.shopify.com/en/manual/your-account/staff-accounts",
    "https://help.shopify.com/en/manual/fulfillment/managing-fulfillments",
    "https://help.shopify.com/en/manual/payments/chargebacks",
]


def extract_text_from_html(html: str, url: str = "") -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["nav", "footer", "script", "style", "aside", "header",
                     ".sidebar", ".breadcrumb", ".related", ".feedback"]):
        tag.decompose()

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True).split("|")[0].strip()

    main = (soup.find("main") or soup.find("article") or
            soup.find("div", class_=re.compile(r"content|article|main|body", re.I)))
    text_source = main or soup.body or soup

    text = text_source.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text[:8000]  # cap at 8k chars

    return {
        "title": title or url,
        "text": text,
        "product_area": _guess_product_area(url),
    }


def _guess_product_area(url: str) -> str:
    path = urlparse(url).path.lower()
    mapping = {
        "payments": "payments", "shipping": "shipping", "orders": "orders",
        "products": "products", "apps": "apps", "themes": "themes",
        "analytics": "analytics", "marketing": "marketing", "customers": "customers",
        "inventory": "inventory", "discount": "marketing", "billing": "billing",
        "taxes": "billing", "checkout": "orders", "fulfillment": "orders",
        "chargebacks": "payments", "domains": "general", "staff": "general",
    }
    for key, val in mapping.items():
        if key in path:
            return val
    return "general"


async def fetch_url(url: str) -> dict | None:
    """Fetch a URL with retries and browser headers."""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(
                timeout=20,
                headers=HEADERS,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    content = extract_text_from_html(resp.text, url)
                    if len(content["text"]) > 200:  # valid content
                        return content
                elif resp.status_code in (403, 429):
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None
        except Exception as e:
            if attempt == 2:
                print(f"[crawler] Failed {url}: {e}")
            await asyncio.sleep(1)
    return None


async def discover_shopify_urls(
    base_url: str = None,
    max_pages: int = None,
    sections: list[str] = None,
) -> list[str]:
    """Return curated Shopify help URLs (sitemap often blocked)."""
    max_pages = max_pages or settings.shopify_scrape_max_pages

    # Try sitemap first
    base_url = base_url or settings.shopify_help_center_url
    sitemap_url = f"{base_url}/sitemap.xml"
    urls = []

    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(sitemap_url)
            if resp.status_code == 200 and "<loc>" in resp.text:
                soup = BeautifulSoup(resp.text, "xml")
                target_sections = sections or ["/en/manual", "/en/partners"]
                for loc in soup.find_all("loc"):
                    url = loc.get_text(strip=True)
                    if any(sec in url for sec in target_sections):
                        urls.append(url)
                    if len(urls) >= max_pages:
                        break
                if urls:
                    print(f"[crawler] Sitemap: found {len(urls)} URLs")
                    return urls
    except Exception as e:
        print(f"[crawler] Sitemap failed: {e}")

    # Fallback to curated list
    print(f"[crawler] Using curated URL list ({len(SHOPIFY_CURATED_URLS)} URLs)")
    return SHOPIFY_CURATED_URLS[:max_pages]
