import asyncio
import json
import os
from urllib.parse import urlencode, urlparse, parse_qs
import pandas as pd
import httpx
from scrapling.fetchers import StealthyFetcher

# Constants
SAF_WELCOME = "https://www.safeway.com"
CONFIG_FILE = 'scraplingAdaptationHana/.safeway_config.json'
CATEGORIES_FILE = 'safeway_categories.json'
OUTPUT_CSV = 'bread_bakery_scraped.csv'

async def gather_scrape_config():
    """Capture session data by monitoring API requests"""
    async def page_action(page):
        captured_request = None
        
        def handle_request(request):
            nonlocal captured_request
            if "/xapi/v1/aisles/products" in request.url:
                captured_request = request
                print(f"✅ Captured API request!")
        
        page.on("request", handle_request)
        
        await page.goto(SAF_WELCOME, timeout=20000)
        print("🌐 Please manually:")
        print("   1. Set your store/ZIP code")
        print("   2. Navigate to ANY bread & bakery subcategory")
        print("   3. The script will automatically detect the API call")
        
        # Wait for the request with timeout
        max_wait = 120  # 2 minutes
        waited = 0
        while not captured_request and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 0.5
        
        if not captured_request:
            print("❌ Timeout waiting for API request")
            return None
        
        try:
            print("🎉 Processing captured request...")
            
            # Extract query params
            parsed = urlparse(captured_request.url)
            raw_params = parse_qs(parsed.query)
            query_params = {k: v[0] for k, v in raw_params.items()}
            
            # Extract cookies and headers
            cookies = await page.context.cookies()
            cookie_jar = {c['name']: c['value'] for c in cookies if 'safeway.com' in c['domain']}
            
            # Clean headers - filter out None values
            raw_headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en',
                'user-agent': captured_request.headers.get('user-agent'),
                'referer': captured_request.headers.get('referer'),
                'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'priority': 'u=1, i'
            }
            
            # Filter out None values
            headers = {k: v for k, v in raw_headers.items() if v is not None}
            
            # Save config
            config = {
                'query_params': query_params,
                'headers': headers,
                'cookies': cookie_jar
            }
            
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"✅ Saved scrape config to {CONFIG_FILE}")
            return page
            
        except Exception as e:
            print(f"❌ Error processing request: {e}")
            return None
    
    await StealthyFetcher.async_fetch(
        url=SAF_WELCOME,
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )

async def scrape_single_category(client, base_params, category_id, category_name, max_items=300):
    """Scrape a single category with pagination handling"""
    seen_upcs = set()
    items = []
    start = 0
    rows = 20  # Items per page
    next_token = None
    
    print(f"🍞 Scraping {category_name} (ID: {category_id})...")
    
    while len(items) < max_items:
        # Build parameters for this request
        params = base_params.copy()
        params.update({
            'category-id': category_id,
            'category-name': category_name,
            'start': str(start),
            'rows': str(rows)
        })
        
        if next_token:
            params['nextPageToken'] = next_token
        
        # Build URL
        url = 'https://www.safeway.com/abs/pub/xapi/v1/aisles/products?' + urlencode(params)
        
        print(f"📄 Fetching page starting at item {start}...")
        
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            
            data = resp.json().get('response', {})
            print(data)
            docs = data.get('docs', [])
            
            if not docs:
                print("📭 No more items found")
                break
            
            # Process items from this page
            page_items = 0
            for doc in docs:
                upc = doc.get('upc')
                if upc and upc not in seen_upcs:
                    seen_upcs.add(upc)
                    # Add category context
                    doc['category_name'] = category_name
                    doc['category_id'] = category_id
                    items.append(doc)
                    page_items += 1
                    
                    if len(items) >= max_items:
                        break
            
            print(f"✅ Added {page_items} new items (total: {len(items)})")
            
            # Get next page token
            next_token = data.get('nextPageToken')
            if not next_token:
                print("📄 No more pages available")
                break
            
            # Update start for next iteration
            start += rows
            
            # Add delay to avoid rate limiting
            await asyncio.sleep(2)
            
        except httpx.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            if "403" in str(e):
                print("🚫 Got blocked (403) - stopping scrape")
                break
            elif "400" in str(e):
                print("⚠️ Bad request (400) - check parameters")
                break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            break
    
    return items

async def main():
    """Main function to scrape bread & bakery categories"""
    
    # Always generate fresh config
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
        print("🔄 Removed old config file")
    
    print("📦 Gathering fresh store and session info...")
    await gather_scrape_config()
    
    if not os.path.exists(CONFIG_FILE):
        print("❌ Config file was not created. Exiting.")
        return
    
    # Load config
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("❌ Failed to load config. Exiting.")
        return
    
    # Load categories
    try:
        with open(CATEGORIES_FILE) as f:
            categories_map = json.load(f)
    except FileNotFoundError:
        print(f"❌ Categories file {CATEGORIES_FILE} not found.")
        return
    
    # Setup request parameters
    base_params = config['query_params'].copy()
    headers = config['headers'].copy()
    cookies = config.get('cookies', {})
    
    # Ask for subscription key if not already in headers
    if 'ocp-apim-subscription-key' not in headers:
        sub_key = input('🔑 Enter your ocp-apim-subscription-key: ').strip()
        headers['ocp-apim-subscription-key'] = sub_key
    
    # Get bread & bakery categories (excluding "All Bread & Bakery")
    bread_categories = categories_map.get("Bread & Bakery", [])
    target_categories = [cat for cat in bread_categories if "All Bread" not in cat['display_name']]
    
    print(f"🎯 Found {len(target_categories)} bread & bakery subcategories to scrape")
    
    all_items = []
    
    async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30) as client:
        for category in target_categories:
            # Extract category info from href
            parsed = urlparse(category['href'])
            query_params = parse_qs(parsed.query)
            
            # Build category name from URL path
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) >= 3:
                # Convert URL path to category name format
                cat_path = '/'.join(path_parts[2:])  # Skip 'shop/aisles'
                category_name = cat_path.replace('-', ' ').title().replace('/', ' > ')
                
                # Extract category ID if available, otherwise use path-based ID
                category_id = query_params.get('category-id', [cat_path.replace('/', '_')])[0]
            else:
                category_name = category['display_name']
                category_id = category['display_name'].lower().replace(' ', '_')
            
            print(f"\n🗂️ Starting: {category_name}")
            
            try:
                items = await scrape_single_category(
                    client, base_params, category_id, category_name, max_items=300
                )
                all_items.extend(items)
                
                print(f"✅ Completed {category_name}: {len(items)} items")
                
                # Longer delay between categories
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"⚠️ Failed to scrape {category_name}: {e}")
                continue
    
    # Save results
    if all_items:
        df = pd.DataFrame(all_items)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n🎉 Success! Scraped {len(all_items)} total items")
        print(f"📁 Saved to: {OUTPUT_CSV}")
        print(f"🏷️ Unique categories: {df['category_name'].nunique()}")
    else:
        print("❌ No items were scraped")

if __name__ == '__main__':
    asyncio.run(main())