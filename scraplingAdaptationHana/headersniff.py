from scrapling.fetchers import StealthyFetcher
from urllib.parse import urlparse
import asyncio
import httpx
import json
import pandas as pd
import logging, sys, pathlib
import base64, json, urllib.parse

LOG_FILE = pathlib.Path("harris_teeter_scrape.log")
HT_UPC_LIST = ["009800895007"]  # Placeholder UPC list for Harris Teeter
HT_OUTPUT_FILE = "harris_teeter_products.xlsx"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

cookies_for_api = {}  # This will be populated after browser interaction

# --- Placeholder: Page interaction to set location/store ---
async def set_zip_harTeet(page, zipcode):
    print("🛠️ Harris Teeter page setup placeholder (manual interaction required)")
    # You will implement the store selector and cookie grab here.
    # Use await export_cookies_for_httpx(page) to store cookies post interaction.
    global cookies_for_api
    await page.wait_for_selector("button[data-testid = 'CurrentModality-button']", timeout = 5000)
    await page.click("button[data-testid = 'CurrentModality-button']", timeout = 5000)
    await page.wait_for_selector("button[data-testid = 'ModalityOption-Button-PICKUP']", timeout = 5000)
    await page.click("button[data-testid = 'ModalityOption-Button-PICKUP']", timeout = 5000)
    await page.fill("input[data-testid='PostalCodeSearchBox-input']", zipcode, timeout = 5000)
    await page.click("button[aria-label = 'Search']", timeout = 5000)
    print("✅ search clicked")
    await page.wait_for_selector("button[data-testid = 'SelectStore-09700352']", timeout = 5000)
    await page.wait_for_selector("button[data-testid = 'SelectStore-09700352']", timeout = 5000)
    await page.click("button[data-testid = 'SelectStore-09700352']", timeout = 5000)
    await page.wait_for_timeout(1000)

    cookies_for_api = await export_cookies_for_httpx(page)
    # for name, val in cookies_for_api.items():
    #     print(f"🍪\n{name}:")
    #     print(decode_cookie_value(val))
    print("🍪 Cookies for API:", cookies_for_api)

# --- Cookie export for Harris Teeter domain ---
async def export_cookies_for_httpx(page, cookie_names=None):
    jar = {}
    for c in await page.context.cookies():
        if not c["domain"].endswith("harristeeter.com"):
            continue
        if cookie_names is None or c["name"] in cookie_names:
            jar[c["name"]] = c["value"]
    return jar

# --- Main async runner to open browser and prepare session ---
async def main(urlstr):
    url = urlstr
    domain = urlparse(url).netloc.replace("www.", "")
    ht_locstr = "20002"

    async def page_action(page):
        if domain in ZIP_HANDLERS:
            await ZIP_HANDLERS[domain](page, ht_locstr)
        else:
            print(f"No handler for domain: {domain}")
        return page

    await StealthyFetcher.async_fetch(
        url=url,
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )

# --- Fetch Harris Teeter product data using UPCs ---
def fetch_harris_teeter_api(cookies, upc_list):
    url = "https://www.harristeeter.com/atlas/v1/product/v2/products"
    params = {
        "filter.verified": "true",
        "projections": "items.full,offers.compact,nutrition.label"
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Origin": "https://www.harristeeter.com",
        "Referer": "https://www.harristeeter.com",
         "x-requested-with": "XMLHttpRequest",
    }
    headers.update({
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    })

    data_out = []
    with httpx.Client(headers=headers, cookies=cookies, timeout=15) as c:
        for upc in upc_list:
            log.info(f"🔍 Fetching UPC {upc}")
            p = params.copy()
            p["filter.gtin13s"] = upc
            try:
                r = c.get(url, params=p)
                r.raise_for_status()
                res = r.json
                print(r.status_code, r.text)
                # for item in res.get("data", []):
                #     data_out.append({
                #         "UPC": upc,
                #         "Name": item.get("description"),
                #         "Brand": item.get("brand"),
                #         "Price": item.get("offers", {}).get("compact", {}).get("price", {}).get("price"),
                #     })
            except Exception as e:
                log.warning(f"❌ Failed to fetch {upc}: {e}")
    return pd.DataFrame(data_out)

from playwright.async_api import async_playwright

async def dump_api_with_browser(url, cookies):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(url)
        await page.wait_for_timeout(3000)

        # Set cookies manually if needed (not needed if page already has them)
        # await context.add_cookies([...])

        response = await page.request.get(
            "https://www.harristeeter.com/atlas/v1/product/v2/products",
            params={
                "filter.gtin13s": "009800895007",
                "filter.verified": "true",
                "projections": "items.full,offers.compact,nutrition.label"
            }
        )
        print(await response.json())
        await browser.close()


# def decode_cookie_value(cookie_value):
#     try:
#         # Step 1: URL decode (if encoded)
#         decoded = urllib.parse.unquote(cookie_value)

#         # Step 2: Add padding for base64 if needed
#         if len(decoded) % 4 != 0:
#             decoded += '=' * (4 - len(decoded) % 4)

#         # Step 3: Try base64-decode
#         raw = base64.b64decode(decoded)

#         # Step 4: Try to parse as JSON
#         try:
#             return json.loads(raw)
#         except json.JSONDecodeError:
#             return raw.decode("utf-8", errors="replace")

#     except Exception as e:
#         return f"⚠️ Could not decode: {e}"

# --- Store scraper setup ---
ZIP_HANDLERS = {
    "harristeeter.com": set_zip_harTeet
}

# --- Main orchestrator ---
if __name__ == "__main__":
    url = "https://www.harristeeter.com"
    asyncio.run(main(url))
    asyncio.run(dump_api_with_browser(url, cookies_for_api))

    # df = fetch_harris_teeter_api(cookies_for_api, HT_UPC_LIST)
    # df.to_excel(HT_OUTPUT_FILE, index=False)
    # print(f"✅ Saved product data to {HT_OUTPUT_FILE}")
