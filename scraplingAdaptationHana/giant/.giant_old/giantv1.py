from scrapling.fetchers import StealthyFetcher
import asyncio
import json
import random

# Test UPC (Nutella from your example)
TEST_UPC = "009800895007"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
]

def build_giant_url(upc):
    """Build Giant Foods API URL for UPC lookup"""
    base_url = "https://giantfood.com/api/v6.0/products/2/50000351"
    params = (
        f"?sort=bestMatch+asc"
        f"&filter="
        f"&start=0"
        f"&flags=true"
        f"&keywords={upc}"
        f"&nutrition=false"
        f"&facetExcludeFilter=true"
        f"&semanticSearch=false"
        f"&dtmCookieId="
        f"&adSessionId=39858261-350a-4b65-b6c0-acf6fb21ae9f"
        f"&platform=desktop"
        f"&includeSponsoredProducts=true"
        f"&adPositions=0,2,3,6,8,10,12"
        f"&facet=categories,brands,nutrition,sustainability,specials,newArrivals,privateLabel"
    )
    return base_url + params

async def fetch_giant_product(upc, page):
    """Fetch single product from Giant Foods API"""
    url = build_giant_url(upc)
    ctx_cookies = await page.context.cookies("https://giantfood.com")
    cookie_hdr = "; ".join(f"{c['name']}={c['value']}" for c in ctx_cookies)
    print(f"🍪 Cookies for API: {cookie_hdr}")
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en,en-US;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': f'https://giantfood.com/product-search/{upc}?searchRef=&semanticSearch=false',
        'sec-ch-device-memory': '8',
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-arch': 'x86',
        'sec-ch-ua-full-version-list': '"Chromium";v="136.0.7103.114", "Google Chrome";v="136.0.7103.114", "Not.A/Brand";v="99.0.0.0"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'cookie': cookie_hdr,
    }
    
    try:
        print(f"🔍 Fetching UPC: {upc}")
        print(f"📡 URL: {url}")
        
        response = await page.context.request.get(url, headers=headers)
        print(f"📊 Status: {response.status}")
        
        if response.status == 200:
            data = await response.json()
            print("✅ Response received!")
            print(f"📄 Raw response preview: {json.dumps(data, indent=2)[:500]}...")
            
            # Parse the response based on your example structure
            if 'response' in data and 'products' in data['response']:
                products = data['response']['products']
                print(f"🛍️ Found {len(products)} products")
                
                results = []
                for product in products:
                    result = {
                        'upc': product.get('upc', ''),
                        'name': product.get('name', ''),
                        'size': product.get('size', ''),
                        'price': product.get('price', ''),
                        'regular_price': product.get('regularPrice', ''),
                        'brand': product.get('brand', ''),
                        'description': f"{product.get('brand', '')} {product.get('name', '')} {product.get('size', '')}".strip()
                    }
                    results.append(result)
                    print(f"✅ Product: {result['description']} - ${result['price']}")
                
                return results
            else:
                print("⚠️ Unexpected response structure")
                return None
                
        elif response.status in [429, 403, 503]:
            print(f"🚫 Rate limited with status {response.status}")
            return None
        else:
            print(f"❌ Request failed with status {response.status}")
            response_text = await response.text()
            print(f"📄 Error response: {response_text[:200]}...")
            return None
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

async def create_stealth_context(browser):
    """Create stealth browser context"""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={'width': random.randint(1200, 1920), 'height': random.randint(800, 1080)},
        extra_http_headers={
            'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.9', 'en-CA,en;q=0.9']),
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
        }
    )
    return context

async def test_single_product():
    """Test fetching a single product"""
    url = "https://giantfood.com"
    
    async def page_action(page):
        print("🚀 Starting Giant Foods product test...")
        
        # Navigate to Giant Foods first to establish session
        print("📱 Navigated to Giant Foods")
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
        
        # Try fetching the test product
        result = await fetch_giant_product(TEST_UPC, page)
        
        if result:
            print(f"🎉 Success! Retrieved {len(result)} products:")
            for product in result:
                print(f"  📦 {product['description']}")
                print(f"  💰 Price: ${product['price']}")
                print(f"  🏷️ UPC: {product['upc']}")
                print(f"  📏 Size: {product['size']}")
                print("  " + "-"*50)
        else:
            print("❌ Failed to retrieve product")
        
        return page
    
    await StealthyFetcher.async_fetch(
        url=url,
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )

if __name__ == "__main__":
    print("🧪 Testing Giant Foods single product lookup...")
    asyncio.run(test_single_product())