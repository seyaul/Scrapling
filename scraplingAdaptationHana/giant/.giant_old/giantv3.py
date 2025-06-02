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

async def fetch_upc_via_playwright(upc_list):
    async def page_action(page):
        # Store all API responses
        api_responses = []
        
        # Set up response listener for ALL requests
        async def handle_response(response):
            if "/api/v6.0/products" in response.url:
                try:
                    data = await response.json()
                    api_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'data': data
                    })
                    print(f"📡 Captured API response: {response.url}")
                except Exception as e:
                    print(f"❌ Error parsing response: {e}")
        
        # Attach the listener
        page.on("response", handle_response)
        
        # 1) Navigate to Giant homepage
        await page.goto("https://giantfood.com", timeout=30000)

        # 2) Fill in your ZIP code and submit
        await page.wait_for_selector('button.robot-shopping-mode-location', timeout=30000)
        await page.click('button.robot-shopping-mode-location', timeout=5000)
        await page.fill("input[name='zipCode']", "20010")  
        await page.click('#search-location', timeout=5000)
        await page.wait_for_timeout(1000)
        address = page.locator("li", has_text="1345 Park Road N.W.")
        await address.locator("button").click(timeout=7000)
        # Wait a moment for any initial loading
        await page.wait_for_timeout(7000)
        print("🌐 Giant Foods location selected, sending request now...")

        results = []
        for idx, upc in enumerate(upc_list):
            print(f"\n🔍 [{idx+1}/{len(upc_list)}] Fetching product for UPC: {upc}")
            search_url = f"https://giantfood.com/product-search/{upc}?semanticSearch=false"
            
            # Clear previous responses
            api_responses.clear()
            
            try:
                # Navigate and wait for the page to load
                await page.goto(search_url, timeout=30000)
                
                # Wait for the API call to complete
                # Try multiple strategies to ensure we catch the response
                
                # Strategy 1: Wait for network idle
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                # Strategy 2: If no response yet, wait a bit more
                if not api_responses:
                    print("⏳ Waiting for API response...")
                    await page.wait_for_timeout(3000)
                
                # Strategy 3: Check if product elements are visible
                # This ensures the API has returned data
                # try:
                #     await page.wait_for_selector(".product-card", timeout=5000)
                # except:
                #     print("⚠️ No product cards found on page")
                
                # Process the captured responses
                if api_responses:
                    # Get the most recent successful response
                    valid_responses = [r for r in api_responses if r['status'] == 200]
                    if valid_responses:
                        response_data = valid_responses[-1]['data']
                        print(f"✅ Found {len(valid_responses)} valid API responses")
                        
                        response = response_data.get('response', {})
                        products = response.get("products", [])
                        
                        if products:
                            product = products[0]
                            results.append({
                                'price': product.get('price'),
                                'upc': product.get('upc'),
                                'size': product.get('size'),
                                'name': product.get('name')
                            })
                            print(f"✅ Successfully fetched: {product.get('name', 'Unknown')} - ${product.get('price', 'N/A')}")
                        else:
                            print(f"⚠️ No products found in API response for UPC: {upc}")
                            break
                    else:
                        print(f"❌ No successful API responses for UPC: {upc}")
                        break
                else:
                    print(f"❌ No API responses captured for UPC: {upc}")
                    break
                    
            except PlaywrightTimeoutError as e:
                print(f"❌ Timeout error for UPC {upc}: {e}")
                break
            except Exception as e:
                print(f"❌ Error fetching UPC {upc}: {e}")
                import traceback
                traceback.print_exc()
                break
                
            # Random delay between requests
            delay = random.uniform(2.0, 5.0)
            print(f"💤 Waiting {delay:.1f} seconds before next request...")
            await asyncio.sleep(delay)

        # Save results if any were collected
        if results:
            df = pd.DataFrame(results)
            df.to_excel(OUTPUT_DATA, index=False)
            print(f"\n📊 Saved {len(results)} products to {OUTPUT_DATA}")
        else:
            print("\n❌ No products were successfully fetched")
        
        # Print debug info
        print(f"\n📈 Summary: {len(results)}/{len(upc_list)} products fetched successfully")
        
        return results

    # launch the browser and run the above page_action
    results = await StealthyFetcher.async_fetch(
        url="https://giantfood.com",
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )
    
    return results


if __name__ == "__main__":
    src_data = pd.read_excel(SOURCE_DATA)
    upc_list = src_data['UPC'].tolist()
    print(f"📦 Found {len(upc_list)} UPCs to process.")
    
    # For testing, you might want to limit to just a few UPCs
    # upc_list = upc_list[:3]  # Uncomment to test with just 3 products
    
    asyncio.run(fetch_upc_via_playwright(upc_list))