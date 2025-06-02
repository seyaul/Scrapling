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
                'ocp-apim-subscription-key': 'e914eec9448c4d5eb672debf5011cf8f',
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
            print(f"🔍 Request URL: {url}")
            resp = await client.get(url)
            resp.raise_for_status()
            
            # Debug the response
            response_text = resp.text
            print(f"📊 Response status: {resp.status_code}")
            print(f"📊 Response length: {len(response_text)}")
            
            try:
                json_data = resp.json()
                print(f"📊 JSON keys: {list(json_data.keys())}")
                
                data = json_data.get('response', {})
                print(f"🔍 DEBUG - response keys: {list(data.keys())}")
                print(f"🔍 DEBUG - numFound: {data.get('numFound')}")
                print(f"🔍 DEBUG - start: {data.get('start')}")
                print(f"🔍 DEBUG - nextPageToken: {data.get('nextPageToken')}")
                print(f"🔍 DEBUG - miscInfo: {data.get('miscInfo', {}).keys()}")
                
                docs = data.get('docs', [])
                print(f"📊 Found {len(docs)} docs")
                
                # If no docs, let's see what we got
                if not docs:
                    print(f"📊 Full response: {json_data}")
                    print("📭 No more items found")
                    break
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                print(f"📊 Raw response: {response_text[:500]}...")
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
                    
                    if page_items <= 3:  # Only print first 3 per page to avoid spam
                        print(f"    📊 UPC sample: {upc} (type: {type(upc)})")

                    if len(items) >= max_items:
                        break
            
            print(f"✅ Added {page_items} new items (total: {len(items)})")
            
            # Get next page token
            next_token = data.get('miscInfo',{}).get('nextPageToken')
            if not next_token or next_token == "":
                print("📄 No more pages available")
                break
            
            # Update start for next iteration
            start += rows
            
            # Add delay to avoid rate limiting
            #await asyncio.sleep(2)
            
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            print(f"❌ HTTP Status Error: {status}")
            if status == 403:
                print("🚫 Got blocked (403) - propagating throttle exception")
                raise     # <-- let this bubble up
            elif status == 400:
                print("⚠️ Bad request (400) - stopping this category")
                break
        except httpx.HTTPError as e:
            # catch other HTTP errors (e.g. timeouts) here if you want
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

# Add this before your main() function

async def main():
    """Main function to scrape all categories"""
    
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
    
    # Load enhanced categories
    try:
        with open(CATEGORIES_FILE) as f:
            categories_map = json.load(f)
    except FileNotFoundError:
        print(f"❌ Enhanced categories file {CATEGORIES_FILE} not found.")
        return
    
    # Setup request parameters
    base_params = config['query_params'].copy()
    headers = config['headers'].copy()
    cookies = config.get('cookies', {})
    
    # Ask for subscription key if not already in headers
    if 'ocp-apim-subscription-key' not in headers:
        sub_key = input('🔑 Enter your ocp-apim-subscription-key: ').strip()
        headers['ocp-apim-subscription-key'] = sub_key
    
    all_items = []
    
    # Load progress
    progress = load_progress()
    print(f"📈 Loaded progress: {len(progress['completed_categories'])} completed, {len(progress['failed_categories'])} failed")

    # Count total subcategories for progress tracking
    total_subcats = sum(len(subcats) for subcats in categories_map.values())
    total_with_ids = sum(1 for subcats in categories_map.values() for subcat in subcats if subcat.get('category_id'))
    completed_count = len(progress['completed_categories'])

    print(f"🎯 Total subcategories: {total_subcats}")
    print(f"🎯 With valid category IDs: {total_with_ids}")
    print(f"🎯 Starting from: {completed_count}/{total_with_ids}")

    all_items = []
    throttled = False

    async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30) as client:
        try:
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
                            
                            # Append to dump file immediately
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
                            print("🚫 Throttled by server (403) — stopping everything.")
                            throttled = True
                            break  # this breaks out of the subcat loop
                        else:
                            print(f"⚠️ HTTP error {e.response.status_code} on {category_name}, skipping.")
                            progress['failed_categories'].append(category_name)
                            save_progress(progress)
                            continue   
                    except Exception as e:
                        error_msg = str(e)
                        print(f"⚠️ Failed to scrape {category_name}: {error_msg}")
                        
                        # Check for 403 throttling
                        if "403" in error_msg:
                            print(f"🚫 Got throttled (403)! Stopping all scraping.")
                            print(f"📊 Progress saved. Resume by running script again.")
                            throttled = True
                            break
                        
                        # Mark as failed
                        progress['failed_categories'].append({
                            'category': category_key,
                            'reason': error_msg,
                            'timestamp': pd.Timestamp.now().isoformat()
                        })
                        
                        # Save progress
                        save_progress(progress)
                        continue
        except httpx.HTTPError as e:
            if "403" in str(e).upper():
                print("🚫 Throttled by server! Stopping scraping.")
                throttled = True
            else:  
                raise e  # Re-raise other HTTP errors

    if throttled:
        print(f"\n🛑 Scraping stopped due to throttling")
        print(f"📊 Completed: {len(progress['completed_categories'])}/{total_with_ids} categories")
        print(f"📁 Products saved to: {DUMP_FILE}")
        print(f"🔄 Run script again to resume from where you left off")
    else:
        print(f"\n🎉 All categories completed!")
    
    # Save results
    # Final results
    if os.path.exists(DUMP_FILE):
        df = pd.read_csv(DUMP_FILE)
        
        # Print UPC samples for format analysis
        print(f"\n🔍 UPC Format Analysis:")
        upc_samples = df['upc'].dropna().head(10).tolist()
        for i, upc in enumerate(upc_samples, 1):
            print(f"   {i}. UPC: {upc} (type: {type(upc)}, length: {len(str(upc))})")
        
        print(f"\n📊 Final Results:")
        print(f"📁 Total items scraped: {len(df)}")
        print(f"📁 Data saved to: {DUMP_FILE}")
        print(f"🏷️ Parent categories: {df['parent_category'].nunique()}")
        print(f"🏷️ Subcategories: {df['category_name'].nunique()}")
        print(f"🏷️ Unique UPCs: {df['upc'].nunique()}")
        
        if progress['failed_categories']:
            print(f"\n❌ Failed categories: {len(progress['failed_categories'])}")
            for failure in progress['failed_categories'][-5:]:  # Show last 5 failures
                print(f"   • {failure['category']}: {failure['reason']}")
    else:
        print("❌ No items were scraped")

if __name__ == '__main__':
    asyncio.run(main())