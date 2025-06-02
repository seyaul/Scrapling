import asyncio
import json
import os
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
import pandas as pd
from scrapling.fetchers import StealthyFetcher

# Constants
SAF_WELCOME = "https://www.safeway.com"
AISLES_URL = "https://www.safeway.com/shop/aisles.html"
CONFIG_FILE = 'scraplingAdaptationHana/.safeway_config.json'
CATEGORIES_FILE = 'safeway_categories.json'
OUTPUT_CSV = 'scraped_all_categories.csv'

async def gather_scrape_config():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    async def page_action(page):
        captured_request = None
    
        # 1) Set up the listener FIRST
        def handle_request(request):
            nonlocal captured_request
            if "/xapi/v1/aisles/products" in request.url:
                captured_request = request
                print("✅ Captured API request!", captured_request)
        
        page.on("request", handle_request)
        # 1) Navigate to homepage
        await page.goto(SAF_WELCOME, timeout=20000)
        print("🌐 Please manually set your store/ZIP and click into any aisle. Then return here and press Enter...")
        max_wait = 120  # 2 minutes
        waited = 0
        while not captured_request and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 0.5
        
        if not captured_request:
            print("❌ Timeout waiting for API request")
            return None
        
        try:
            print("🎉 Got the API request! Processing...")
            
            # Add null check
            if not captured_request or not captured_request.url:
                print("❌ Invalid request object")
                return None
            
            # Extract query params
            parsed = urlparse(captured_request.url)
            raw_params = parse_qs(parsed.query)
            query_params = {k: v[0] for k, v in raw_params.items()}
            
            # Extract cookies and headers
            cookies = await page.context.cookies()
            cookie_jar = {c['name']: c['value'] for c in cookies if 'safeway.com' in c['domain']}
            
            headers = {
                'accept': captured_request.headers.get('accept'),
                'user-agent': captured_request.headers.get('user-agent'),
                'referer': captured_request.headers.get('referer'),
            }
            
            # Save config
            config = {
                'query_params': query_params,
                'headers': headers,
                'cookies': cookie_jar
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"✅ Saved scrape config to {CONFIG_FILE}")
            return page
            
        except Exception as e:
            print(f"❌ Error processing request: {e}")
            import traceback
            traceback.print_exc()
            return None

    # Launch a headed session for manual steps
    await StealthyFetcher.async_fetch(
        url=SAF_WELCOME,
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )

async def fetch_items_for_category(client, base_params, max_items):
    seen_upcs = set()
    items = []
    next_token = None
    while len(items) < max_items:
        params = base_params.copy()
        if next_token:
            params['nextPageToken'] = next_token
        url = 'https://www.safeway.com/abs/pub/xapi/v1/aisles/products?' + urlencode(params)
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json().get('response', {})
        for doc in data.get('docs', []):
            upc = doc.get('upc')
            if upc and upc not in seen_upcs:
                seen_upcs.add(upc)
                items.append(doc)
                if len(items) >= max_items:
                    break
        next_token = data.get('nextPageToken')
        if not next_token:
            break
    return items

async def main(max_items_per=300):
    # 🔁 Always force fresh config generation
    if not os.path.exists(CONFIG_FILE):
        print("📦 No config found, gathering store and session info...")
        await gather_scrape_config()

    # 🧩 Load config once generated
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("❌ Failed to load config. Exiting.")
        return

    base_params = config['query_params']
    headers = config['headers']
    cookies = config.get('cookies', {})

    # 🔐 Ask for subscription key if not set
    sub_key = config.get('subscription_key') or os.getenv('SAFEWAY_SUB_KEY')
    if not sub_key:
        sub_key = input('🔑 Enter your ocp-apim-subscription-key: ').strip()
    headers['ocp-apim-subscription-key'] = sub_key

    # 📁 Load categories
    with open(CATEGORIES_FILE) as f:
        categories_map = json.load(f)

    all_items = []
    async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=20) as client:
        for parent_cat, subcats in categories_map.items():
            for sub in subcats:
                parsed = urlparse(sub['href'])
                qs = parse_qs(parsed.query)
                cat_id = qs.get('category-id', [''])[0]
                cat_name = qs.get('category-name', [''])[0]
                params = base_params.copy()
                params['category-id'] = cat_id
                params['category-name'] = cat_name
                print(f"🗂️ Scraping {parent_cat} > {sub['display_name']} ({cat_id})...")
                try:
                    items = await fetch_items_for_category(client, params, max_items_per)
                    for it in items:
                        it['parent_category'] = parent_cat
                        it['subcategory'] = sub['display_name']
                    all_items.extend(items)
                except httpx.HTTPError as e:
                    print(f"⚠️ Failed to scrape {sub['display_name']}: {e}")

    df = pd.DataFrame(all_items)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Done. Scraped {len(all_items)} items into {OUTPUT_CSV}")


if __name__ == '__main__':
    asyncio.run(main())
