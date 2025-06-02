import asyncio
import json
from scrapling.fetchers import StealthyFetcher
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import random
import pandas as pd

SOURCE_DATA = "scraplingAdaptationHana/source_prices.xlsx"
OUTPUT_DATA = "harris_teeter_results.xlsx"
CHECKPOINT_FILE = "scraping_checkpoint_giant.json"
TEMP_RESULTS_FILE = "temp_session_results_giant.json"

async def fetch_upc_via_playwright(upc: str):
    async def page_action(page):
        # 1) Navigate to Giant homepage
        await page.goto("https://giantfood.com", timeout=30000)

        # 2) Fill in your ZIP code and submit
        #    (update these selectors if Giant changes them)
        await page.wait_for_selector('button.robot-shopping-mode-location', timeout=30000)
        await page.click('button.robot-shopping-mode-location', timeout=5000)
        await page.fill("input[name='zipCode']", "20010")  
        await page.click('#search-location', timeout = 5000)
        await page.wait_for_timeout(1000)
        address = page.locator("li", has_text="1345 Park Road N.W.")
        await address.locator("button").click(timeout=5000)
        # Wait a moment for any initial loading
        await page.wait_for_timeout(5000)
        print("🌐 Giant Foods location selected, sending request now...")
        # 6) Wait for the API call to fire, then grab its JSON
        await page.goto(f"https://giantfood.com/product-search/{upc}?semanticSearch=false",
                    timeout=30000)

        # 2) Grab the API response via the context
        try:
            resp = await page.context.wait_for_event(
                "response",
                predicate=lambda r: "/api/v6.0/products" in r.url and r.status == 200,
                timeout=15000
            )
        except PlaywrightTimeoutError:
            print("❌ Timed out waiting for the products API response.")
            return

        # 3) Pull the JSON
        data = await resp.json()
        print(json.dumps(data, indent=2))
        return page


    # launch the browser and run the above page_action
    await StealthyFetcher.async_fetch(
        url="https://giantfood.com",
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )

async def fetch_all_products(upc_list):
    results = []
    for upc in upc_list:
        print(f"🔍 Fetching product for UPC: {upc}")
        try:
            data = await fetch_upc_via_playwright(upc)
            product = data['response']['products'][0] if data and 'products' in data['response'] else None
            if product:
                results.append({
                    'price': product['price'],
                    'upc': product['upc'],
                    'size': product['size'],
                    'name': product['name']
                })
        except Exception as e:
            print(f"❌ Error fetching UPC {upc}: {e}")
        await asyncio.sleep(random.uniform(1.0, 10.0))  


if __name__ == "__main__":
    src_data = pd.read_excel(SOURCE_DATA)
    upc_list = src_data['UPC'].tolist()
    #asyncio.run(fetch_upc_via_playwright(upc_list))
    asyncio.run(fetch_upc_via_playwright('009800895007'))  # Example ZIP code, change as needed
