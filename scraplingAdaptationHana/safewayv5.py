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
CATEGORIES_FILE = 'enhanced_safeway_categories.json'
OUTPUT_CSV = 'bread_bakery_scraped.csv'
PROGRESS_FILE = 'scrape_progress.json'
DUMP_FILE = 'scraped_products_dump.csv'

async def gather_scrape_config(max_retries=3):
    """Capture session data by monitoring API requests with retry mechanism"""
    
    for attempt in range(max_retries):
        print(f"🔄 Configuration attempt {attempt + 1}/{max_retries}")
        
        try:
            async def page_action(page):
                captured_request = None
                
                def handle_request(request):
                    nonlocal captured_request
                    if "/xapi/v1/aisles/products" in request.url:
                        captured_request = request
                        print(f"✅ Captured API request!")
                
                page.on("request", handle_request)
                
                await page.goto(SAF_WELCOME, timeout=20000)
                await page.wait_for_selector('div[id="openFulfillmentModalButton"]', timeout=20000)
                await page.click('div[id="openFulfillmentModalButton"]')
                await page.fill("input[data-qa='hmpg-flfllmntmdl-zpcdtxtbx']", "20007")
                await page.keyboard.press("Enter")
                await page.click('a[aria-describedby*="address_2912"]')
                await page.wait_for_timeout(1000)
                await page.goto("https://www.safeway.com/shop/aisles/bread-bakery/sandwich-breads.html?sort=&page=1&loc=2912")
                
                # Wait for the request with timeout
                max_wait = 120
                waited = 0
                while not captured_request and waited < max_wait:
                    await asyncio.sleep(0.5)
                    waited += 0.5
                
                if not captured_request:
                    raise Exception("Timeout waiting for API request")
                
                print("🎉 Processing captured request...")
                
                # Extract query params
                parsed = urlparse(captured_request.url)
                raw_params = parse_qs(parsed.query)
                query_params = {k: v[0] for k, v in raw_params.items()}
                
                # Extract cookies and headers
                cookies = await page.context.cookies()
                cookie_jar = {c['name']: c['value'] for c in cookies if 'safeway.com' in c['domain']}
                
                # Clean headers
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
                    'ocp-apim-subscription-key': 'e914eec9448c4d5eb672debf5011cf8f',
                    'priority': 'u=1, i'
                }
                
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
            
            # Use StealthyFetcher with fresh context
            await StealthyFetcher.async_fetch(
                url=SAF_WELCOME,
                headless=False,
                network_idle=True,
                block_images=False,
                disable_resources=False,
                page_action=page_action
            )

            # If we get here, configuration was successful
            if os.path.exists(CONFIG_FILE):
                return True
            else:
                raise Exception("Config file was not created")
                
        except Exception as e:
            print(f"❌ Configuration attempt {attempt + 1} failed: {e}")
            
            # Clean up any partial config file
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1)  # Progressive backoff: 30s, 60s, 90s
                print(f"⏳ Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ All configuration attempts failed")
                return False
    
    return False

async def create_http_client(config):
    """Create HTTP client with config"""
    headers = config['headers'].copy()
    cookies = config.get('cookies', {})
    
    # Ask for subscription key if not already in headers
    if 'ocp-apim-subscription-key' not in headers:
        sub_key = input('🔑 Enter your ocp-apim-subscription-key: ').strip()
        headers['ocp-apim-subscription-key'] = sub_key
    
    return httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30)

async def scrape_single_category(client, base_params, category_id, category_name, max_items=300):
    """Scrape a single category with pagination handling"""
    seen_upcs = set()
    items = []
    start = 0
    rows = 20
    next_token = None
    
    print(f"🍞 Scraping {category_name} (ID: {category_id})...")
    
    while len(items) < max_items:
        params = base_params.copy()
        params.update({
            'category-id': category_id,
            'category-name': category_name,
            'start': str(start),
            'rows': str(rows)
        })
        
        if next_token:
            params['nextPageToken'] = next_token
        
        url = 'https://www.safeway.com/abs/pub/xapi/v1/aisles/products?' + urlencode(params)
        
        print(f"📄 Fetching page starting at item {start}...")
        
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            
            response_text = resp.text
            print(f"📊 Response status: {resp.status_code}")
            
            try:
                json_data = resp.json()
                data = json_data.get('response', {})
                docs = data.get('docs', [])
                
                if not docs:
                    print("📭 No more items found")
                    break
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                break
            
            # Process items from this page
            page_items = 0
            for doc in docs:
                upc = doc.get('upc')
                if upc and upc not in seen_upcs:
                    seen_upcs.add(upc)
                    doc['category_name'] = category_name
                    doc['category_id'] = category_id
                    items.append(doc)
                    page_items += 1
                    
                    if len(items) >= max_items:
                        break
            
            print(f"✅ Added {page_items} new items (total: {len(items)})")
            
            # Get next page token
            next_token = data.get('miscInfo',{}).get('nextPageToken')
            if not next_token or next_token == "":
                print("📄 No more pages available")
                break
            
            start += rows
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                print("🚫 Got throttled (403) - raising exception for retry")
                raise  # This will bubble up to trigger context recreation
            elif e.response.status_code == 400:
                print("⚠️ Bad request (400) - stopping this category")
                break
        except httpx.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            break
    
    return items

def load_progress():
    """Load previous scraping progress"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'completed_categories': [], 'failed_categories': [], 'last_parent': None, 'last_subcat': None}

def save_progress(progress):
    """Save current scraping progress"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def append_to_dump(items):
    """Append items to dump file"""
    if items:
        df = pd.DataFrame(items)
        if os.path.exists(DUMP_FILE):
            df.to_csv(DUMP_FILE, mode='a', header=False, index=False)
        else:
            df.to_csv(DUMP_FILE, index=False)

async def scrape_with_throttle_recovery(categories_map, max_retries=999):
    """Main scraping function with automatic throttle recovery"""
    
    # Load progress
    progress = load_progress()
    print(f"📈 Loaded progress: {len(progress['completed_categories'])} completed, {len(progress['failed_categories'])} failed")

    # Count total subcategories
    total_subcats = sum(len(subcats) for subcats in categories_map.values())
    total_with_ids = sum(1 for subcats in categories_map.values() for subcat in subcats if subcat.get('category_id'))
    completed_count = len(progress['completed_categories'])

    print(f"🎯 Total subcategories: {total_subcats}")
    print(f"🎯 With valid category IDs: {total_with_ids}")
    print(f"🎯 Starting from: {completed_count}/{total_with_ids}")

    all_items = []
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            # Generate fresh config for each attempt
            print(f"\n🔄 Attempt {retry_count + 1}/{max_retries + 1} - Getting fresh configuration...")
            
            # Remove old config
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            
            # Get fresh config
            config_success = await gather_scrape_config()
            if not config_success:
                print("❌ Failed to get configuration")
                return False
            
            # Load fresh config
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            
            base_params = config['query_params'].copy()
            
            # Create fresh HTTP client
            async with await create_http_client(config) as client:
                # Continue scraping from where we left off
                throttled = False
                
                for parent_cat, subcats in categories_map.items():
                    if throttled:
                        break
                        
                    print(f"\n📂 Processing parent category: {parent_cat}")
                    
                    for subcat in subcats:
                        if throttled:
                            break
                            
                        # Skip categories without IDs
                        if not subcat.get('category_id'):
                            continue
                        
                        category_key = f"{parent_cat}::{subcat['display_name']}"
                        
                        # Skip if already completed
                        if category_key in progress['completed_categories']:
                            completed_count += 1
                            print(f"⏭️ Skipping completed: {subcat['display_name']} ({completed_count}/{total_with_ids})")
                            continue
                        
                        category_id = subcat['category_id']
                        category_name = subcat['category_name']
                        
                        print(f"\n🗂️ [{completed_count + 1}/{total_with_ids}] Starting: {category_name}")
                        
                        try:
                            items = await scrape_single_category(
                                client, base_params, category_id, category_name, max_items=300
                            )
                            
                            if items:
                                # Add parent category to each item
                                for item in items:
                                    item['parent_category'] = parent_cat
                                
                                all_items.extend(items)
                                append_to_dump(items)
                                
                                print(f"✅ Completed {category_name}: {len(items)} items")
                                
                                # Mark as completed
                                progress['completed_categories'].append(category_key)
                                completed_count += 1
                            else:
                                print(f"⚠️ No items found for {category_name}")
                                progress['failed_categories'].append({
                                    'category': category_key,
                                    'reason': 'No items found',
                                    'timestamp': pd.Timestamp.now().isoformat()
                                })
                            
                            # Save progress after each category
                            save_progress(progress)
                            
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 403:
                                print("🚫 Throttled by server (403) — will recreate context and retry")
                                throttled = True
                                break  # Break out of subcategory loop
                            else:
                                print(f"⚠️ HTTP error {e.response.status_code} on {category_name}, skipping.")
                                progress['failed_categories'].append({
                                    'category': category_key,
                                    'reason': f'HTTP {e.response.status_code}',
                                    'timestamp': pd.Timestamp.now().isoformat()
                                })
                                save_progress(progress)
                                continue
                        
                        except Exception as e:
                            error_msg = str(e)
                            print(f"⚠️ Failed to scrape {category_name}: {error_msg}")
                            
                            # Check for 403 throttling in error message
                            if "403" in error_msg:
                                print(f"🚫 Got throttled (403)! Will recreate context and retry.")
                                throttled = True
                                break
                            
                            # Mark as failed
                            progress['failed_categories'].append({
                                'category': category_key,
                                'reason': error_msg,
                                'timestamp': pd.Timestamp.now().isoformat()
                            })
                            
                            save_progress(progress)
                            continue
                
                # If we completed all categories without throttling, we're done
                if not throttled:
                    print(f"\n🎉 All categories completed successfully!")
                    return True
                
        except Exception as e:
            print(f"❌ Unexpected error in attempt {retry_count + 1}: {e}")
        
        # If we got throttled or had an error, increment retry count
        retry_count += 1
        
        if retry_count <= max_retries:
            # Progressive backoff: wait longer between retries
            wait_time = retry_count   # 60s, 120s, 180s
            print(f"⏳ Throttled! Waiting {wait_time} seconds before recreating context...")
            await asyncio.sleep(wait_time)
        else:
            print(f"\n🛑 Maximum retries ({max_retries}) reached. Stopping.")
            break
    
    # Final status
    print(f"\n📊 Final Status:")
    print(f"✅ Completed: {len(progress['completed_categories'])}/{total_with_ids} categories")
    print(f"❌ Failed: {len(progress['failed_categories'])} categories")
    
    if os.path.exists(DUMP_FILE):
        df = pd.read_csv(DUMP_FILE)
        print(f"📁 Total items scraped: {len(df)}")
        print(f"📁 Data saved to: {DUMP_FILE}")
        print(f"🔄 Run script again to retry failed categories")
    
    return False

async def main():
    """Main function to scrape all categories with throttle recovery"""
    
    # Load enhanced categories
    try:
        with open(CATEGORIES_FILE) as f:
            categories_map = json.load(f)
    except FileNotFoundError:
        print(f"❌ Enhanced categories file {CATEGORIES_FILE} not found.")
        return
    
    # Start scraping with automatic throttle recovery
    success = await scrape_with_throttle_recovery(categories_map, max_retries=999)
    
    if success:
        print("🎉 Scraping completed successfully!")
    else:
        print("⚠️ Scraping completed with some limitations due to throttling")

if __name__ == '__main__':
    asyncio.run(main())