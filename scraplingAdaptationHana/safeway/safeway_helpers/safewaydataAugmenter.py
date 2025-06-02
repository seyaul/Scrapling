import asyncio
import json
import os
from urllib.parse import urlparse, parse_qs
from scrapling.fetchers import StealthyFetcher
import pathlib

# Constants
SAF_WELCOME = "https://www.safeway.com"

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

CATEGORIES_FILE = BASE_DIR / 'safeway_necessary_ppdata/safeway_categories.json'
#CATEGORIES_FILE = 'safeway_categories.json'
ENHANCED_CATEGORIES_FILE = BASE_DIR / 'safeway_necessary_ppdata/enhanced_safeway_categories_test.json'
CONFIG_FILE = BASE_DIR / 'safeway_necessary_ppdata/.safeway_config.json'

async def discover_category_api_call(category_href):
    """Navigate to a category page and capture the API call to get real category ID"""
    captured_data = None
    
    async def page_action(page):
        nonlocal captured_data
        
        def handle_request(request):
            nonlocal captured_data
            if "/xapi/v1/aisles/products" in request.url:
                # Parse the URL to get category info
                parsed = urlparse(request.url)
                params = parse_qs(parsed.query)
                captured_data = {
                    'category_id': params.get('category-id', [''])[0],
                    'category_name': params.get('category-name', [''])[0],
                    'full_url': request.url
                }
                print(f"  ✅ Captured API call with category-id: {captured_data['category_id']}")
        
        page.on("request", handle_request)
        
        try:
            # Navigate to the specific category page
            print(f"  🌐 Navigating to: {category_href}")
            await page.goto(category_href, timeout=20000)
            
            # Wait a bit for the API call to fire
            await asyncio.sleep(2)
            
            return page
            
        except Exception as e:
            print(f"  ❌ Error navigating to {category_href}: {e}")
            return page
    
    try:
        await StealthyFetcher.async_fetch(
            url=category_href,
            headless=True,  # Run in background for speed
            network_idle=True,
            block_images=True,  # Faster loading
            disable_resources=True,
            page_action=page_action
        )
        return captured_data
    except Exception as e:
        print(f"  ❌ Failed to discover category ID for {category_href}: {e}")
        return None

async def enhance_categories_with_ids():
    """Add real category IDs to the categories JSON file"""
    
    # Load existing categories
    try:
        with open(CATEGORIES_FILE) as f:
            categories_map = json.load(f)
        print(f"📁 Loaded {len(categories_map)} parent categories from {CATEGORIES_FILE}")
    except FileNotFoundError:
        print(f"❌ Categories file {CATEGORIES_FILE} not found.")
        return
    
    # Enhanced categories with IDs
    enhanced_categories = {}
    total_subcats = sum(len(subcats) for subcats in categories_map.values())
    processed = 0
    
    print(f"🎯 Total subcategories to process: {total_subcats}")
    print("🚀 Starting category ID discovery...\n")
    
    for parent_cat, subcats in categories_map.items():
        print(f"\n📂 Processing parent category: {parent_cat} ({len(subcats)} subcategories)")
        enhanced_categories[parent_cat] = []
        
        for subcat in subcats:
            processed += 1
            print(f"\n🔍 [{processed}/{total_subcats}] {parent_cat} > {subcat['display_name']}")
            
            # Navigate to category page and capture API call
            category_data = await discover_category_api_call(subcat['href'])
            
            if category_data and category_data['category_id']:
                # Create enhanced subcategory with real IDs
                enhanced_subcat = {
                    'display_name': subcat['display_name'],
                    'href': subcat['href'],
                    'category_id': category_data['category_id'],
                    'category_name': category_data['category_name']
                }
                
                enhanced_categories[parent_cat].append(enhanced_subcat)
                print(f"  ✅ Added ID '{category_data['category_id']}' for {subcat['display_name']}")
                
            else:
                # Keep original data even if we couldn't get the ID
                enhanced_subcat = {
                    'display_name': subcat['display_name'],
                    'href': subcat['href'],
                    'category_id': None,
                    'category_name': None
                }
                enhanced_categories[parent_cat].append(enhanced_subcat)
                print(f"  ❌ Failed to get ID for {subcat['display_name']} - kept original data")
            
            # Rate limiting between requests
            #print(f"  ⏳ Waiting 3 seconds before next category...")
            #await asyncio.sleep(3)
    
    # Save enhanced categories
    with open(ENHANCED_CATEGORIES_FILE, 'w') as f:
        json.dump(enhanced_categories, f, indent=2)
    
    # Print summary
    total_enhanced = 0
    total_failed = 0
    for parent_cat, subcats in enhanced_categories.items():
        for subcat in subcats:
            if subcat['category_id']:
                total_enhanced += 1
            else:
                total_failed += 1
    
    print(f"\n🎉 Enhancement complete!")
    print(f"📁 Enhanced categories saved to: {ENHANCED_CATEGORIES_FILE}")
    print(f"✅ Successfully enhanced: {total_enhanced}/{total_subcats} categories")
    print(f"❌ Failed to enhance: {total_failed}/{total_subcats} categories")
    
    if total_failed > 0:
        print(f"\n⚠️  Some categories failed to enhance. You can:")
        print(f"   1. Re-run this script to retry failed categories")
        print(f"   2. Or manually check those category pages")

async def load_session_config():
    """Load session config if it exists for store context"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            print("📋 Loaded existing session config for store context")
            return config
        except:
            print("⚠️  Could not load session config - proceeding without store context")
    else:
        print("💡 No session config found - make sure you've run the main scraper once")
        print("   The script will still work but might default to a generic store")
    return None

async def main():
    """Main function to enhance categories with real IDs"""
    print("🔧 Safeway Category ID Enhancement Script")
    print("=" * 50)
    
    # Load session config if available
    config = await load_session_config()
    
    # Start the enhancement process
    await enhance_categories_with_ids()
    
    print(f"\n🏁 Script complete! You can now use {ENHANCED_CATEGORIES_FILE} in your scraper.")
    print("💡 Your main scraper can now load category IDs directly without page navigation!")

if __name__ == '__main__':
    asyncio.run(main())