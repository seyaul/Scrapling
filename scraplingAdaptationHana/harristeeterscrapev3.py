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
from RateLimiter import RateLimiter

LOG_FILE = pathlib.Path("harris_teeter_scrape.log")
HT_OUTPUT_FILE = "harris_teeter_products.xlsx"

CACHE_FILE = "scraplingAdaptationHana/upc_data.json"
UPC_DATA = None

QUERIES = ["cheerios", "cinnamon", "apples", "hazelnut", "peanut", "milk", "eggs"]
PREV_QUERY = "nutella"
USER_AGENTs = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
]


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

async def create_stealth_context(browser):
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTs),
        viewport={'width': random.randint(1200, 1920), 'height': random.randint(800, 1080)},
        extra_http_headers={
                    'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.9', 'en-CA,en;q=0.9']),
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1',
                }
    )
    return context


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
    response = await page.context.request.get(
        url,
        headers=common_headers
    )
    print("Status code:", response.status)
    text = await response.text()
    print("Response text: ", text) 
    try:
        data = await response.json()
    except json.JSONDecodeError as e:
        print("❌ Failed to decode JSON response:", e)
        return []
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

ZIP_HANDLERS = {
    "harristeeter.com": set_zip_harTeet
}

async def fetch_all_batches(upc_list, page, laf_object, QUERIES=QUERIES, PREV_QUERY=PREV_QUERY):
    all_results = []
    num_batches = 1
    browser = page.context.browser
    rate_limiter = RateLimiter()
    await page.context.close()
    for batch in batch_gtins(upc_list, batch_size = 25):
        success = False
        retry_count = 0
        max_retries = 3
        while not success and retry_count < max_retries:
            try:
                await rate_limiter.wait_before_request()
                context = await create_stealth_context(browser)
                batch_page = await context.new_page()
                rand_query = random.choice(QUERIES)
                query_url = build_query_url(rand_query)
                print(f"🔍 Batch {num_batches}, Attempt {retry_count + 1}: Navigating to {query_url}")
                await batch_page.goto(query_url, wait_until='networkidle', timeout=10000)
                await asyncio.sleep(random.uniform(2.0, 5.0))
                laf_object = get_laf_token()
                batch_results = await fetch_ht_batch(batch, batch_page, laf_object, query_url=query_url)
                if batch_results:  # If we got results, consider it a success
                    all_results.extend(batch_results)
                    rate_limiter.record_success()
                    success = True
                    print(f"✅ Batch {num_batches} completed with {len(batch_results)} results.")
                else:
                    print(f"⚠️ Batch {num_batches} returned no results, retrying...")
                    retry_count += 1
                    rate_limiter.record_failure()
                await context.close()
            except Exception as e:
                print(f"❌ Error in batch {num_batches}, attempt {retry_count + 1}: {str(e)}")
                retry_count += 1
                rate_limiter.record_failure()
                
                try:
                    await context.close()
                except:
                    pass
                
                if retry_count < max_retries:
                    await asyncio.sleep(random.uniform(30.0, 60.0))  # Longer wait on error
        if not success:
            print(f"💀 Failed to complete batch {num_batches} after {max_retries} attempts")
            return 
        num_batches += 1
    
    print("✅ All batches completed:", json.dumps(all_results, indent=2))
    return all_results

    #     batch_results = await fetch_ht_batch(batch, batch_page, laf_object, query_url=query_url)
    #     all_results.extend(batch_results)
    #     sleep_time = random.uniform(10.0, 20.0)
    #     if prev_time != 0:
    #         while abs(sleep_time - prev_time) < 5.0:
    #             sleep_time = random.uniform(10.0, 20.0)
    #     prev_time = sleep_time
    #     print(f"⏳ Sleeping for {sleep_time:.2f} seconds before next batch...")
    #     rand_query = random.choice(QUERIES)
    #     QUERIES.remove(rand_query)
    #     QUERIES.append(PREV_QUERY)
    #     PREV_QUERY = rand_query
    #     query_url = build_query_url(rand_query)
    #     print("🔍 Navigating to query URL:", query_url)
    #     print(f"Finished batch {num_batches} with {len(batch_results)} results.")
    #     num_batches += 1
    #     prev_context = context
    #     context = await browser.new_context()
    #     batch_page = await context.new_page()
    #     await batch_page.goto(query_url, timeout=10000)
    #     laf_object = get_laf_token()
    #     print("laf_object: ", laf_object)
    #     await asyncio.sleep(sleep_time)
    #     await prev_context.close()
    # print("✅: ", json.dumps(all_results, indent=2))
    # return all_results
    

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

def build_query_url(query):
    base_url = "https://www.harristeeter.com/search"
    suffix = "&searchType=default_search"
    return f"{base_url}?query={urllib.parse.quote(query)}{suffix}"

    
def get_laf_token():
    if not laf_object:
        raise RuntimeError("❌ No laf_object captured. Ensure you clicked the store selector.")
    return laf_object

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

def on_request(request):
    global laf_object
    if "atlas/v1/product/v2/products" in request.url and request.headers.get("x-laf-object"):
        laf_object = request.headers["x-laf-object"]
        print("📦 Captured laf_object")
    return laf_object

def upc_to_gtin13(upc12):
    # drop last digit, pad to 13
    core = upc12[:-1]
    return core.zfill(13)

# --- Main orchestrator ---
if __name__ == "__main__":
    url = "https://www.harristeeter.com"
    asyncio.run(main(url))