import asyncio
import json
import os
from urllib.parse import urlparse, parse_qs
from scrapling.fetchers import StealthyFetcher
import pathlib
import random
from datetime import datetime
import threading
import sys

BASE_FILE = pathlib.Path(__file__).resolve().parent

# File configurations
CATEGORY_MAPPING_FILE = BASE_FILE / "giant_scraping/giant_category_mapping.json"
ZIP_CODE = "20010"
STORE_ADDRESS = "1345 Park Road N.W."

# Global interrupt flag
interrupt_current_category = threading.Event()

def setup_interrupt_handler():
    """Setup keyboard interrupt handler"""
    def input_thread():
        """Thread to monitor for user input"""
        try:
            print("\n🔧 Press 'q' + Enter to skip remaining elements in current category and move to next category...")
            while True:
                user_input = input().strip().lower()
                if user_input == 'q':
                    interrupt_current_category.set()
                    print("\n🛑 Skip requested! Will finish current element and move to next category...")
        except (EOFError, KeyboardInterrupt):
            # Handle case where input is not available
            pass
    
    # Start the input monitoring thread
    input_monitor = threading.Thread(target=input_thread, daemon=True)
    input_monitor.start()

def check_category_skip():
    """Check if user requested to skip current category"""
    return interrupt_current_category.is_set()

def reset_category_skip():
    """Reset the category skip flag for the next category"""
    interrupt_current_category.clear()

# Main categories to discover subcategories for
MAIN_CATEGORIES = {
    "2098": "Produce",
    "1563": "Meat",
    "1633": "Seafood", 
    "921": "Deli & Prepared Food",
    "805": "Dairy & Eggs",
    "85": "Bread & Bakery",
    "365": "Beverages",
    "1066": "Rice, Pasta & Beans",
    "166": "Baking & Cooking",
    "569": "Condiments & Sauces",
    "2708": "Soups & Canned Goods",
    "530": "Breakfast",
    "2543": "Snacks",
    "7099": "Candy & Chocolate",
    "2": "Adult Beverages",
    "1448": "Laundry, Paper & Cleaning",
    "1675": "Home & Office",
    "6477": "Floral & Garden",
    "1201": "Health & Beauty",
    "1370": "Baby",
    "2057": "Pets"
}

# Ensure directories exist
CATEGORY_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)

def analyze_api_request(url, main_category_id):
    """
    Analyze an API request URL to determine if it's a filtered subcategory
    Returns tuple: (is_valid_subcategory, subcategory_info)
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Extract key parameters
        cat_tree_id = params.get('catTreeId', [None])[0]
        keywords = params.get('keywords', [None])[0]
        filter_param = params.get('filter', [''])[0]
        
        # If catTreeId is different and it's a known main category, skip it
        if cat_tree_id and cat_tree_id != str(main_category_id) and cat_tree_id in MAIN_CATEGORIES:
            return False, {"reason": "different_main_category", "cat_tree_id": cat_tree_id}
        
        # Check if this is the same category but with meaningful filters
        if cat_tree_id == str(main_category_id):
            # Look for filtering indicators
            has_keywords = keywords and keywords.strip()
            has_filter = filter_param and filter_param.strip() and filter_param.strip() != ''
            
            # Check for specific filter patterns that indicate subcategories
            filter_indicators = []
            
            if has_keywords:
                filter_indicators.append(f"keywords={keywords}")
            
            if has_filter:
                # Parse common filter patterns
                if 'newArrivals' in filter_param:
                    filter_indicators.append("new_arrivals_filter")
                elif 'specials' in filter_param:
                    filter_indicators.append("specials_filter")
                elif 'organic' in filter_param:
                    filter_indicators.append("organic_filter")
                else:
                    filter_indicators.append(f"custom_filter={filter_param}")
            
            # Check for other meaningful parameters that indicate filtering
            other_params = {}
            for key, values in params.items():
                if key not in ['catTreeId', 'sort', 'start', 'flags', 'substitute', 'nutrition', 
                              'extendedInfo', 'facetExcludeFilter', 'facet', 'dtmCookieId', 
                              'adSessionId', 'platform', 'includeSponsoredProducts'] and values[0]:
                    other_params[key] = values[0]
                    if key not in ['keywords', 'filter']:
                        filter_indicators.append(f"{key}={values[0]}")
            
            # If we have any filtering indicators, this is a valid subcategory
            if filter_indicators:
                return True, {
                    "type": "filtered_subcategory",
                    "cat_tree_id": cat_tree_id,
                    "keywords": keywords,
                    "filter": filter_param,
                    "filter_indicators": filter_indicators,
                    "other_params": other_params
                }
            else:
                # This might be the unfiltered main category call
                return False, {"reason": "unfiltered_main_category"}
        
        # Different category ID that's not a main category = real subcategory
        elif cat_tree_id and cat_tree_id != str(main_category_id):
            return True, {
                "type": "real_subcategory",
                "cat_tree_id": cat_tree_id
            }
        
        # No catTreeId or other edge cases
        else:
            return False, {"reason": "no_category_id"}
            
    except Exception as e:
        return False, {"reason": "parse_error", "error": str(e)}

async def discover_subcategories_for_category(page, main_category_id, main_category_name, existing_data=None):
    """Discover all subcategories for a single main category, with resume capability"""
    
    print(f"\n🔍 Discovering subcategories for {main_category_name} (ID: {main_category_id})")
    print(f"   ⏳ Loading category page...")
    
    # Initialize or load existing progress
    subcategories = existing_data.get('subcategories', []) if existing_data else []
    tested_elements = existing_data.get('tested_elements', []) if existing_data else []
    start_index = len(tested_elements)
    
    if start_index > 0:
        print(f"   🔄 Resuming from element {start_index + 1} (already tested {start_index} elements)")
        print(f"   📊 Current progress: {len(subcategories)} subcategories found so far")
    
    try:
        # Navigate to main category page
        await page.goto(f"https://giantfood.com/browse-aisles/categories/1/categories/{main_category_id}")
        await page.wait_for_timeout(8000)
        
        print(f"   📄 Current URL: {page.url}")
        print(f"   🔍 Searching for subcategory navigation...")
        
        captured_requests = []
        
        # Set up network monitoring with enhanced request capture
        def handle_request(request):
            if "/api/v6.0/products/" in request.url and "catTreeId=" in request.url:
                captured_requests.append({
                    'url': request.url,
                    'timestamp': datetime.now().isoformat(),
                    'method': request.method
                })
        
        def handle_response(response):
            if "/api/v6.0/products/" in response.url and "catTreeId=" in response.url:
                captured_requests.append({
                    'url': response.url,
                    'timestamp': datetime.now().isoformat(),
                    'method': 'RESPONSE',
                    'status': response.status
                })
        
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        # Try to find subcategory navigation using the known good selector first
        pill_elements = []
        found_selector = None
        
        print(f"   🔎 Looking for subcategory navigation...")
        
        try:
            print(f"   [1/1] Testing known good selector: .spyglass-nav-group_wrapper")
            await page.wait_for_selector('.spyglass-nav-group_wrapper', timeout=5000)
            elements = await page.locator('.spyglass-nav-group_wrapper').all()
            if elements:
                pill_elements = elements
                found_selector = '.spyglass-nav-group_wrapper'
                print(f"   ✅ Found {len(elements)} elements with .spyglass-nav-group_wrapper")
            else:
                print(f"   ❌ No elements found with .spyglass-nav-group_wrapper")
        except:
            print(f"   ❌ .spyglass-nav-group_wrapper selector not found")
        
        # Fallback to other selectors only if the primary one fails
        if not pill_elements:
            print(f"   🔄 Primary selector failed, trying fallback selectors...")
            
            fallback_selectors = [
                '.sub-category-pills_item',
                '.subcategory-pill',
                '.category-filter',
                '[data-testid*="subcategory"]',
                '[data-testid*="filter"]',
                '.filter-pill',
                '.nav-pill',
                '.category-content .filter-pill',
                '.content-area button',
                '.filter-section button',
                '.subcategory-section a',
                'main button[data-index]',
                'main a[href*="/select/"]'
            ]
            
            for i, selector in enumerate(fallback_selectors):
                try:
                    print(f"   [{i+1}/{len(fallback_selectors)}] Testing fallback: {selector}")
                    await page.wait_for_selector(selector, timeout=2000)
                    elements = await page.locator(selector).all()
                    if elements:
                        pill_elements = elements
                        found_selector = selector
                        print(f"   ✅ Found {len(elements)} elements with selector: {selector}")
                        break
                    else:
                        print(f"   ❌ No elements found")
                except:
                    print(f"   ❌ Selector not found")
                    continue
        
        if not pill_elements:
            print(f"   🔍 No subcategory pills found with standard selectors.")
            print(f"   🔍 Performing deep search for navigation elements...")
            
            debug_selectors = [
                'main nav li',
                'main .nav li', 
                '.content button',
                '.category-page button',
                'main a[href*="categories"]',
                '.filter-container a',
                '.subcategory-container li'
            ]
            
            for j, debug_selector in enumerate(debug_selectors):
                try:
                    print(f"   [{j+1}/{len(debug_selectors)}] Deep search: {debug_selector}")
                    elements = await page.locator(debug_selector).all()
                    if elements and len(elements) > 1:
                        sample_texts = []
                        valid_elements = []
                        
                        for elem in elements[:10]:
                            try:
                                text = await elem.inner_text(timeout=2000)
                                href = await elem.get_attribute('href', timeout=2000) or ''
                                
                                if text and text.strip():
                                    text = text.strip()
                                    
                                    # Filter out main category names and common navigation
                                    if (text.lower() not in [cat.lower() for cat in MAIN_CATEGORIES.values()] and
                                        text.lower() not in ['home', 'account', 'cart', 'search', 'menu', 'sign in', 'browse all'] and
                                        len(text) < 50 and  # Avoid long descriptions
                                        # Check if it's within the current category (URL check)
                                        (not href or main_category_id in href or '/select/' in href)):
                                        sample_texts.append(text)
                                        valid_elements.append(elem)
                            except Exception as e:
                                print(f"     ⚠️ Timeout getting text for element: {e}")
                                pass
                        
                        if sample_texts and len(valid_elements) >= 2:
                            print(f"   🎯 Found {len(valid_elements)} potential subcategories: {sample_texts[:5]}")
                            
                            subcategory_keywords = ['organic', 'fresh', 'new', 'special', 'sale', 'local', 'frozen', 'canned', 'packaged', 'cut', 'prepared']
                            if any(keyword in ' '.join(sample_texts).lower() for keyword in subcategory_keywords):
                                print(f"   ✅ These look like real subcategories! Using selector: {debug_selector}")
                                pill_elements = valid_elements
                                found_selector = debug_selector
                                break
                            else:
                                print(f"   ⚠️ These might not be subcategories, continuing search")
                except Exception as e:
                    print(f"   ❌ Error with selector '{debug_selector}': {e}")
                    continue
        
        if not pill_elements:
            print(f"   📭 No subcategory navigation found for {main_category_name}")
            return subcategories, tested_elements, "completed"
        
        print(f"   🎯 Testing {len(pill_elements)} elements with selector: {found_selector}")
        
        # Filter out elements that might be the current/active page or main categories
        clickable_pills = []
        for i, pill in enumerate(pill_elements):
            try:
                text = await pill.inner_text(timeout=3000)
                class_list = await pill.get_attribute('class', timeout=3000) or ''
                href = await pill.get_attribute('href', timeout=3000) or ''
                
                if text and text.strip():
                    text = text.strip()
                    
                    if (not ('active' in class_list.lower() or 'current' in class_list.lower()) and
                        text.lower() not in [cat.lower() for cat in MAIN_CATEGORIES.values()] and
                        text.lower() not in ['featured', 'all', 'browse', 'home', 'account', 'cart'] and
                        len(text) < 50 and
                        (not href or main_category_id in href or '/select/' in href or 'categories' not in href)):
                        clickable_pills.append((i, pill, text))
                        
            except Exception as e:
                print(f"   ⚠️ Skipping element {i} due to timeout: {e}")
                continue
        
        print(f"   🖱️ Found {len(clickable_pills)} valid subcategory elements to test")
        
        # Track the initial/unfiltered request to compare against
        initial_requests = list(captured_requests)
        
        # Wait a bit to capture any initial page load requests
        await page.wait_for_timeout(2000)
        print(f"   📊 Captured {len(captured_requests)} initial API requests")
        
        # Start from the resume index
        elements_to_test = clickable_pills[start_index:] if start_index < len(clickable_pills) else []
        
        if start_index > 0:
            print(f"   ⏭️ Skipping first {start_index} elements (already tested)")
            print(f"   🎯 Will test {len(elements_to_test)} remaining elements")
        
        for pill_index, (i, pill, pill_text) in enumerate(elements_to_test):
            actual_index = start_index + pill_index
            
            # Check for user skip request
            if check_category_skip():
                print(f"\n🛑 Category skip detected! Marking remaining {len(elements_to_test) - pill_index} elements as 'not found'...")
                
                # Mark all remaining elements as tested with "skipped" status
                for remaining_index in range(pill_index, len(elements_to_test)):
                    remaining_i, remaining_pill, remaining_text = elements_to_test[remaining_index]
                    tested_elements.append({
                        'index': remaining_i,
                        'text': remaining_text,
                        'skipped': True,
                        'tested_at': datetime.now().isoformat()
                    })
                    print(f"   ⏭️ Marked '{remaining_text}' as skipped")
                
                print(f"📊 Skipped {len(elements_to_test) - pill_index} elements, continuing with {len(subcategories)} subcategories found")
                break
            
            try:
                print(f"   🖱️ [{actual_index+1}/{len(clickable_pills)}] Testing: '{pill_text}'")
                
                # Clear previous requests but keep initial ones for comparison
                requests_before_click = list(captured_requests)
                
                # Check if this element might navigate to a new page
                try:
                    href = await pill.get_attribute('href', timeout=5000)
                    is_link = href and href.strip()
                except:
                    href = None
                    is_link = False
                
                if is_link:
                    print(f"       🔗 Element is a link to: {href}")
                    # For links, we need to navigate and wait for the API call
                    try:
                        await pill.click(timeout=10000)
                        await page.wait_for_timeout(6000)  # Wait longer for navigation
                    except Exception as e:
                        print(f"       ❌ Click failed: {e}")
                        # Mark this element as tested even if it failed
                        tested_elements.append({
                            'index': i,
                            'text': pill_text,
                            'error': str(e),
                            'tested_at': datetime.now().isoformat()
                        })
                        continue
                    
                    # Check if we're on a new page
                    current_url = page.url
                    if f"/{main_category_id}/" not in current_url:
                        print(f"       📄 Navigated to new page: {current_url}")
                        # Wait a bit more for API calls on the new page
                        await page.wait_for_timeout(3000)
                else:
                    print(f"       🖱️ Element is a button/clickable element")
                    # For buttons, click and wait for API response
                    try:
                        await pill.click(timeout=10000)
                        await page.wait_for_timeout(4000)
                    except Exception as e:
                        print(f"       ❌ Click failed: {e}")
                        # Mark this element as tested even if it failed
                        tested_elements.append({
                            'index': i,
                            'text': pill_text,
                            'error': str(e),
                            'tested_at': datetime.now().isoformat()
                        })
                        continue
                
                # Find new requests after the click
                new_requests = [req for req in captured_requests if req not in requests_before_click]
                
                # Also check if there are any recent requests that might be relevant
                if not new_requests:
                    print(f"       🔍 No new requests found, checking recent requests...")
                    # Look at the last few requests to see if any are relevant
                    recent_requests = captured_requests[-5:] if len(captured_requests) >= 5 else captured_requests
                    for req in recent_requests:
                        # Check if this request might be related to our click
                        if "/api/v6.0/products/" in req['url'] and "catTreeId=" in req['url']:
                            # Parse the catTreeId to see if it's different from main category
                            parsed = urlparse(req['url'])
                            params = parse_qs(parsed.query)
                            cat_tree_id = params.get('catTreeId', [None])[0]
                            
                            if cat_tree_id and cat_tree_id != str(main_category_id):
                                print(f"       🎯 Found potentially relevant recent request with catTreeId={cat_tree_id}")
                                new_requests = [req]
                                break
                
                # Mark this element as tested
                tested_elements.append({
                    'index': i,
                    'text': pill_text,
                    'tested_at': datetime.now().isoformat(),
                    'found_api_request': len(new_requests) > 0
                })
                
                if new_requests:
                    latest_request = new_requests[-1]
                    url = latest_request['url']
                    
                    print(f"       📡 Captured API request: {url[:100]}...")
                    
                    # Use our enhanced analysis function
                    is_valid, analysis_result = analyze_api_request(url, main_category_id)
                    
                    if is_valid:
                        subcategory_data = {
                            'name': pill_text,
                            'index': i,
                            'discovered_at': datetime.now().isoformat(),
                            'selector_used': found_selector,
                            'api_url': url,
                            'is_link': is_link,
                            'href': href if is_link else None
                        }
                        
                        # Add analysis results to subcategory data
                        subcategory_data.update(analysis_result)
                        
                        # Create user-friendly type description
                        if analysis_result['type'] == 'filtered_subcategory':
                            filter_descriptions = []
                            if analysis_result.get('keywords'):
                                filter_descriptions.append(f"keyword search: '{analysis_result['keywords']}'")
                            if analysis_result.get('filter'):
                                filter_descriptions.append(f"filter: '{analysis_result['filter']}'")
                            if analysis_result.get('other_params'):
                                for k, v in analysis_result['other_params'].items():
                                    filter_descriptions.append(f"{k}: '{v}'")
                            
                            subcategory_data['description'] = f"Filtered view ({', '.join(filter_descriptions)})"
                            print(f"     ✅ Valid filtered subcategory: {pill_text}")
                            print(f"        Filters: {', '.join(filter_descriptions)}")
                            
                        elif analysis_result['type'] == 'real_subcategory':
                            subcategory_data['description'] = f"Real subcategory (ID: {analysis_result['cat_tree_id']})"
                            print(f"     ✅ Real subcategory: {pill_text} → catTreeId={analysis_result['cat_tree_id']}")
                        
                        subcategories.append(subcategory_data)
                        
                    else:
                        reason = analysis_result.get('reason', 'unknown')
                        print(f"     ⚠️ Skipping '{pill_text}' - {reason}")
                        if 'cat_tree_id' in analysis_result:
                            print(f"        (refers to category {analysis_result['cat_tree_id']})")
                else:
                    print(f"     ⚠️ No API request captured for '{pill_text}'")
                    print(f"        Total requests before: {len(requests_before_click)}")
                    print(f"        Total requests after: {len(captured_requests)}")
                    
                    # Try to provide debugging info
                    if len(captured_requests) > 0:
                        last_request = captured_requests[-1]
                        print(f"        Last captured request: {last_request['url'][:50]}...")
                
                # If we navigated to a new page, go back to the main category page
                current_url = page.url
                if f"/categories/{main_category_id}" not in current_url:
                    print(f"       ⬅️ Returning to main category page")
                    await page.goto(f"https://giantfood.com/browse-aisles/categories/1/categories/{main_category_id}")
                    await page.wait_for_timeout(3000)
                
                # Progress indicator
                print(f"     ⏳ Progress: {actual_index+1}/{len(clickable_pills)} tested")
                
                # Check for skip request before delay
                if check_category_skip():
                    print(f"🛑 Category skip detected during delay! Will skip remaining elements after this one...")
                    # Don't break here, let the loop condition handle it on next iteration
                
                # Delay between clicks
                await asyncio.sleep(random.uniform(2, 4))
                
            except Exception as e:
                print(f"     ❌ Error testing element '{pill_text}': {e}")
                # Mark this element as tested even if it failed
                tested_elements.append({
                    'index': i,
                    'text': pill_text,
                    'error': str(e),
                    'tested_at': datetime.now().isoformat()
                })
                continue
        
        # Remove the request listeners
        page.remove_listener("request", handle_request)
        page.remove_listener("response", handle_response)
        
        # Check if discovery was skipped
        discovery_status = "skipped" if check_category_skip() else "completed"
        
        if discovery_status == "skipped":
            print(f"   ⏭️ Category skipped by user! Found {len(subcategories)} valid subcategories for {main_category_name}")
        else:
            print(f"   ✅ Discovery complete! Found {len(subcategories)} valid subcategories for {main_category_name}")
        
        # Show summary of what was found
        if subcategories:
            by_type = {}
            for sub in subcategories:
                sub_type = sub['type']
                if sub_type not in by_type:
                    by_type[sub_type] = 0
                by_type[sub_type] += 1
            
            print(f"   📊 Summary: {', '.join(f'{count} {type_name}' for type_name, count in by_type.items())}")
            
            # Show examples of what was found
            for sub in subcategories[:3]:  # Show first 3 as examples
                print(f"      • {sub['name']}: {sub.get('description', 'No description')}")
        
        return subcategories, tested_elements, discovery_status
        
    except Exception as e:
        print(f"   ❌ Error discovering subcategories for {main_category_name}: {e}")
        return subcategories, tested_elements, "error"

async def discover_all_categories():
    """Discover subcategories for all main categories"""
    
    async def page_action(page):
        # Set up Giant Foods location first
        print("🌐 Setting up Giant Foods location...")
        await page.goto("https://giantfood.com", timeout=30000)
        
        try:
            # await page.wait_for_selector('button.robot-shopping-mode-location', timeout=30000)
            # await page.click('button.robot-shopping-mode-location', timeout=5000)
            # await page.fill("input[name='zipCode']", ZIP_CODE)  
            # await page.click('#search-location', timeout=5000)
            # await page.wait_for_timeout(1000)
            # address = page.locator("li", has_text=STORE_ADDRESS)
            # await address.locator("button").click(timeout=7000)
            # await page.wait_for_timeout(5000)
            print("✅ Giant Foods location selected")
        except Exception as e:
            print(f"⚠️ Warning: Could not set location: {e}")
            print("Continuing anyway...")
        
        # Discover subcategories for each main category
        all_category_mapping = {}
        total_categories = len(MAIN_CATEGORIES)
        
        # Load existing progress if it exists
        if os.path.exists(CATEGORY_MAPPING_FILE):
            try:
                with open(CATEGORY_MAPPING_FILE, 'r') as f:
                    all_category_mapping = json.load(f)
                completed_categories = []
                in_progress_categories = []
                failed_categories = []
                
                for cat_id, data in all_category_mapping.items():
                    if 'error' in data:
                        failed_categories.append(cat_id)
                    elif data.get('status') == 'completed':
                        completed_categories.append(cat_id)
                    elif 'tested_elements' in data:
                        in_progress_categories.append(cat_id)
                
                print(f"📂 Found existing progress:")
                if completed_categories:
                    print(f"   ✅ Completed: {len(completed_categories)} categories")
                    print(f"      {', '.join(all_category_mapping[cat_id]['name'] for cat_id in completed_categories)}")
                if in_progress_categories:
                    print(f"   🔄 In progress: {len(in_progress_categories)} categories")
                    print(f"      {', '.join(all_category_mapping[cat_id]['name'] for cat_id in in_progress_categories)}")
                if failed_categories:
                    print(f"   ❌ Failed (will retry): {len(failed_categories)} categories")
                    print(f"      {', '.join(all_category_mapping[cat_id]['name'] for cat_id in failed_categories)}")
                    
            except Exception as e:
                print(f"⚠️ Could not load existing progress: {e}")
                all_category_mapping = {}
        
        print(f"\n🚀 Starting discovery for {total_categories} main categories")
        print("=" * 60)
        
        # Setup interrupt handler
        setup_interrupt_handler()
        
        for category_index, (main_cat_id, main_cat_name) in enumerate(MAIN_CATEGORIES.items(), 1):
            # Reset category skip flag for each new category
            reset_category_skip()
            
            # Skip if already completed successfully
            if (main_cat_id in all_category_mapping and 
                all_category_mapping[main_cat_id].get('status') == 'completed'):
                print(f"\n📂 [{category_index}/{total_categories}] Skipping {main_cat_name} (already completed)")
                continue
                
            # Check if this category was in progress or failed
            resume_info = ""
            if main_cat_id in all_category_mapping:
                existing_data = all_category_mapping[main_cat_id]
                if 'tested_elements' in existing_data:
                    tested_count = len(existing_data['tested_elements'])
                    resume_info = f" (resuming from element {tested_count + 1})"
                elif 'error' in existing_data:
                    resume_info = " (retrying after previous failure)"
                
            print(f"\n📂 [{category_index}/{total_categories}] Processing: {main_cat_name}{resume_info}")
            print(f"   🔄 Overall progress: {((category_index-1)/total_categories)*100:.1f}% complete")
            
            try:
                subcategories, tested_elements, status = await discover_subcategories_for_category(
                    page, main_cat_id, main_cat_name, all_category_mapping.get(main_cat_id)
                )
                
                all_category_mapping[main_cat_id] = {
                    'name': main_cat_name,
                    'subcategories': subcategories,
                    'tested_elements': tested_elements,
                    'discovered_at': datetime.now().isoformat(),
                    'total_subcategories': len(subcategories),
                    'status': status
                }
                
                if status == "completed":
                    print(f"   ✅ Category {category_index}/{total_categories} complete: {len(subcategories)} subcategories found")
                elif status == "skipped":
                    print(f"   ⏭️ Category {category_index}/{total_categories} skipped: {len(subcategories)} subcategories found")
                elif status == "error":
                    print(f"   ⚠️ Category {category_index}/{total_categories} had errors but saved progress: {len(subcategories)} subcategories found")
                
                # Save progress after each category (in case of crashes)
                temp_mapping = {k: v for k, v in all_category_mapping.items()}
                with open(CATEGORY_MAPPING_FILE, 'w') as f:
                    json.dump(temp_mapping, f, indent=2)
                print(f"   💾 Progress saved ({category_index}/{total_categories} categories)")
                
                # Delay between main categories (no interrupt check here - always continue to next category)
                if category_index < total_categories:
                    wait_time = random.uniform(8, 15)
                    print(f"   ⏳ Waiting {wait_time:.1f}s before next category...")
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                print(f"   ❌ Failed to process {main_cat_name}: {e}")
                # Save what we have so far, marking as error but preserving any progress
                existing_data = all_category_mapping.get(main_cat_id, {})
                all_category_mapping[main_cat_id] = {
                    'name': main_cat_name,
                    'subcategories': existing_data.get('subcategories', []),
                    'tested_elements': existing_data.get('tested_elements', []),
                    'error': str(e),
                    'discovered_at': datetime.now().isoformat(),
                    'total_subcategories': len(existing_data.get('subcategories', [])),
                    'status': 'error'
                }
        
        # Final status message - always complete now since we don't terminate early
        print(f"\n🎯 Discovery phase complete!")
        print("=" * 60)
        
        # Save the complete mapping
        with open(CATEGORY_MAPPING_FILE, 'w') as f:
            json.dump(all_category_mapping, f, indent=2)
        
        print(f"\n🎉 Category discovery complete!")
        print(f"📁 Mapping saved to: {CATEGORY_MAPPING_FILE}")
        
        # Print summary
        total_subcategories = sum(data['total_subcategories'] for data in all_category_mapping.values())
        successful_categories = sum(1 for data in all_category_mapping.values() if data.get('status') == 'completed')
        skipped_categories = sum(1 for data in all_category_mapping.values() if data.get('status') == 'skipped')
        
        print(f"\n📊 Discovery Summary:")
        print(f"   Main categories processed: {len(all_category_mapping)}")
        print(f"   Successful discoveries: {successful_categories}")
        if skipped_categories > 0:
            print(f"   Skipped categories: {skipped_categories}")
        print(f"   Total subcategories found: {total_subcategories}")
        if len(all_category_mapping) > 0:
            print(f"   Average subcategories per category: {total_subcategories / len(all_category_mapping):.1f}")
        
        # Show breakdown by category
        print(f"\n📋 Breakdown by category:")
        for cat_id, data in all_category_mapping.items():
            status = data.get('status', 'unknown')
            if status == 'completed':
                status_icon = "✅"
            elif status == 'skipped':
                status_icon = "⏭️"
            elif status == 'error':
                status_icon = "⚠️"
            else:
                status_icon = "🔄"
            
            tested_info = ""
            if 'tested_elements' in data:
                tested_count = len(data['tested_elements'])
                skipped_count = sum(1 for elem in data['tested_elements'] if elem.get('skipped', False))
                if tested_count > 0:
                    if skipped_count > 0:
                        tested_info = f" ({tested_count - skipped_count} tested, {skipped_count} skipped)"
                    else:
                        tested_info = f" ({tested_count} elements tested)"
            
            print(f"   {status_icon} {data['name']}: {data['total_subcategories']} subcategories{tested_info}")
            
            if 'error' in data and status == 'error':
                print(f"      Error: {data['error']}")
        
        return page
    
    # Run the discovery
    await StealthyFetcher.async_fetch(
        url="https://giantfood.com",
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )

def load_category_mapping():
    """Load the discovered category mapping"""
    if os.path.exists(CATEGORY_MAPPING_FILE):
        with open(CATEGORY_MAPPING_FILE, 'r') as f:
            return json.load(f)
    return {}

def show_category_summary():
    """Show summary of discovered categories"""
    mapping = load_category_mapping()
    
    if not mapping:
        print("❌ No category mapping found. Run discovery first.")
        return
    
    print("📊 Giant Foods Category Mapping Summary")
    print("=" * 50)
    
    total_subcategories = 0
    for cat_id, data in mapping.items():
        print(f"\n📂 {data['name']} (ID: {cat_id})")
        subcats = data.get('subcategories', [])
        total_subcategories += len(subcats)
        
        if 'error' in data:
            print(f"   ❌ Error: {data['error']}")
            continue
            
        if not subcats:
            print("   📭 No subcategories found")
            continue
        
        # Group by type
        by_type = {}
        for subcat in subcats:
            subcat_type = subcat.get('type', 'unknown')
            if subcat_type not in by_type:
                by_type[subcat_type] = []
            by_type[subcat_type].append(subcat)
        
        for subcat_type, items in by_type.items():
            print(f"   📁 {subcat_type}: {len(items)} items")
            for item in items[:3]:  # Show first 3
                desc = item.get('description', item['name'])
                print(f"     • {item['name']}: {desc}")
            if len(items) > 3:
                print(f"     ... and {len(items) - 3} more")
    
    print(f"\n🎯 Total: {len(mapping)} main categories, {total_subcategories} subcategories")

async def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "summary":
            show_category_summary()
            return
        elif sys.argv[1] == "discover":
            pass  # Continue to discovery
        else:
            print("Usage:")
            print("  python giant_category_discovery.py discover - Run category discovery")
            print("  python giant_category_discovery.py summary  - Show discovered categories")
            return
    
    print("🔍 Starting Giant Foods Category Discovery")
    print("=" * 50)
    
    await discover_all_categories()
    
    print("\n✅ Discovery complete! Run with 'summary' to see results.")

if __name__ == "__main__":
    asyncio.run(main())