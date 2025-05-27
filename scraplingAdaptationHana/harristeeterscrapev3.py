from scrapling.fetchers import StealthyFetcher
from urllib.parse import urlparse
import asyncio
import httpx
import json
import pandas as pd
import logging, sys, pathlib
import base64, json, urllib.parse
import os
import random

LOG_FILE = pathlib.Path("harris_teeter_scrape.log")
HT_OUTPUT_FILE = "harris_teeter_products.xlsx"

CACHE_FILE = "scraplingAdaptationHana/upc_data.json"
UPC_DATA = None

laf_object = None  

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        try:
            UPC_DATA = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Cache file exists but is invalid or empty. Starting fresh.")
            UPC_DATA = {}
else: UPC_DATA = {}


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

def upc_to_gtin13(upc12):
    # drop last digit, pad to 13
    core = upc12[:-1]
    return core.zfill(13)

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
   
    
    page.on("request", on_request)  
    await page.goto("https://www.harristeeter.com/search?query=nutella&searchType=default_search", timeout=10000)
    await page.wait_for_timeout(4000)

    if not laf_object:
        raise RuntimeError("❌ No laf_object captured from requests. Ensure you clicked the store selector.")

    await page.wait_for_timeout(1000)

    #cookies_for_api = await export_cookies_for_httpx(page)
    # for name, val in cookies_for_api.items():
    #     print(f"🍪\n{name}:")
    #     print(decode_cookie_value(val))
    #print("🍪 Cookies for API:", cookies_for_api)
    #print("UPC_DATA.keys():", list(UPC_DATA.keys()))
    await fetch_all_batches(upc_list=list(UPC_DATA.keys()), page=page, laf_object=laf_object)

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

async def fetch_ht_batch(gtin_list, page, laf_object, query_url):
    url = build_ht_url(gtin_list)
    results = []
    common_headers = {
        "Accept": "application/json, text/plain, */*",
        'accept-language': 'en,en-US;q=0.9',
        'cache-control': 'no-cache',

        "x-laf-object": laf_object,
        # if you see other required xtests in your DevTools XHR, copy them here:
        'device-memory': '8',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': query_url,
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'user-time-zone': 'America/New_York',
        "x-ab-test": '[{"testVersion":"B","testID":"5388ca","testOrigin":"cb"}]',
        "x-call-origin": '{"component":"internal search","page":"internal search"}',
        "x-facility-id": "09700352",
        'x-geo-location-v1': '{"id":"b9c9c75e-930e-4073-9f2b-cee2aa4fa318","proxyStore":"09700819"}',
        "x-kroger-channel": "WEB",
        'x-modality': '{"type":"PICKUP","locationId":"09700352"}',
        'x-modality-type': 'PICKUP'
    }
    #for upc in upc_list:
    # for upc in range(10, 20):
    #     gtin13 = upc_to_gtin13(upc_list[upc])
    #     url = (
    #         "https://www.harristeeter.com/atlas/v1/product/v2/products"
    #         f"?filter.gtin13s={gtin13}"
    #         "&filter.verified=true"
    #         "&projections=items.full,offers.compact,nutrition.label,variantGroupings.compact"
    #     )

    #     response = await page.context.request.get(
    #         url,
    #         headers=common_headers
    #     )
    #     data = await response.json()
    #     if response.status != 200:
    #         print(await response.text())
    #     print("⮞ HTTP", response.status, "payload:", json.dumps(data, indent=2))
    #     prod = data["data"]["products"][0]
    #     pickup_summary = next((summary for summary in prod["fulfillmentSummaries"] if summary["type"] == "PICKUP"), None)
    #     if pickup_summary:
    #         results.append({
    #             "upc": upc_list[upc],
    #             "price": pickup_summary["regular"]["price"],
    #             "size": pickup_summary["regular"]["pricePerUnitString"],
    #             #"desc": prod["description"],
    #         }
    #         )
    #     results.append(prod["item"]["description"])
    #     print("✅: ", json.dumps(results, indent=2))
    #     await page.wait_for_timeout(500 + random.randint(0, 500))

    #url = build_test_url(upc_list)
    #print("full url: ", url)
    response = await page.context.request.get(
        url,
        headers=common_headers
    )
    print("Status code:", response.status)
    text = await response.text()
    print("Response text: ") 
    try:
        data = await response.json()
    except json.JSONDecodeError as e:
        print("❌ Failed to decode JSON response:", e)
        return []
    #print("⮞ HTTP", response.status, "payload:", json.dumps(data, indent=2))
    # prod = data["data"]["products"][0]
    # pickup_summary = next((summary for summary in prod["fulfillmentSummaries"] if summary["type"] == "PICKUP"), None)
    # results.append(prod["item"]["upc"])
    # if pickup_summary:
    #     results.append({
    #         #"upc": upc_list[upc],
    #         "price": pickup_summary["regular"]["price"],
    #         "size": pickup_summary["regular"]["pricePerUnitString"],
    #         #"desc": prod["description"],
    #     }
    #     )
    #results.append(prod["item"]["description"])
    for prod in data["data"]["products"]:
        pickup_summary = next((summary for summary in prod["fulfillmentSummaries"] if summary["type"] == "PICKUP"), None)
        if pickup_summary:
            results.append({
                "upc": prod["item"]["upc"],
                "price": pickup_summary["regular"]["price"],
                "size": pickup_summary["regular"]["pricePerUnitString"],
                "description": prod["item"]["description"]
            })
        else:
            results.append({
                "upc": prod["item"]["upc"],
                "price": None,
                "size": None,
                "description": prod["item"]["description"]
            })
    
    print("✅: ", json.dumps(results, indent=2))
    
    return results

def on_request(request):
    global laf_object
    if "atlas/v1/product/v2/products" in request.url and request.headers.get("x-laf-object"):
        laf_object = request.headers["x-laf-object"]
        print("📦 Captured laf_object")
    return laf_object

ZIP_HANDLERS = {
    "harristeeter.com": set_zip_harTeet
}

QUERIES = ["cheerios", "cinnamon", "apples", "hazelnut", "peanut", "milk", "eggs"]
PREV_QUERY = "nutella"

def batch_gtins(gtin_list, batch_size=26):
    for i in range(0, len(gtin_list), batch_size):
        yield gtin_list[i:i + batch_size]

def build_ht_url(gtin_batch):
    #gtin_batch = [upc_to_gtin13(upc) for upc in upc_list[:25]]
    base_url = "https://www.harristeeter.com/atlas/v1/product/v2/products"
    gtin_params = "&".join([f"filter.gtin13s={upc_to_gtin13(gtin)}" for gtin in gtin_batch])
    suffix = (
        "&filter.verified=true"
        "&projections=items.full,offers.compact,nutrition.label,variantGroupings.compact"
    )
    full_url = f"{base_url}?{gtin_params}{suffix}"
    return full_url

async def fetch_all_batches(upc_list, page, laf_object, QUERIES=QUERIES, PREV_QUERY=PREV_QUERY):
    all_results = []
    num_batches = 1
    prev_time = 0
    laf_object = get_laf_token()
    browser = page.context.browser
    query_url = "https://www.harristeeter.com/search?query=nutella&searchType=default_search"
    for batch in batch_gtins(upc_list, batch_size = 25):
        context = await browser.new_context()
        batch_page = await context.new_page()
        
        batch_results = await fetch_ht_batch(batch, batch_page, laf_object, query_url=query_url)
        all_results.extend(batch_results)
        sleep_time = random.uniform(10.0, 20.0)
        if prev_time != 0:
            while abs(sleep_time - prev_time) < 5.0:
                sleep_time = random.uniform(10.0, 20.0)
        prev_time = sleep_time
        print(f"⏳ Sleeping for {sleep_time:.2f} seconds before next batch...")
        rand_query = random.choice(QUERIES)
        QUERIES.remove(rand_query)
        QUERIES.append(PREV_QUERY)
        PREV_QUERY = rand_query
        query_url = build_query_url(rand_query)
        print("🔍 Navigating to query URL:", query_url)
        print(f"Finished batch {num_batches} with {len(batch_results)} results.")
        num_batches += 1
        laf_object = await batch_page.goto(query_url, timeout=10000)
        print("laf_object: ", laf_object)
        await context.close()
        await asyncio.sleep(sleep_time)
    print("✅: ", json.dumps(all_results, indent=2))
    return all_results

def build_query_url(query):
    base_url = "https://www.harristeeter.com/search"
    suffix = "&searchType=default_search"
    return f"{base_url}?query={urllib.parse.quote(query)}{suffix}"
    
def get_laf_token():
    if not laf_object:
        raise RuntimeError("❌ No laf_object captured. Ensure you clicked the store selector.")
    return laf_object

# --- Main orchestrator ---
if __name__ == "__main__":
    url = "https://www.harristeeter.com"
    asyncio.run(main(url))