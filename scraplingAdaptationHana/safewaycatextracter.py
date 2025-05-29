import asyncio
import json
from scrapling.fetchers import StealthyFetcher

# URL for Safeway's main aisles page
AISLES_URL = "https://www.safeway.com/shop/aisles.html"

async def extract_categories(page):
    # Navigate to the aisles page
    print("🌐 Navigating to Safeway aisles page...")
    await page.goto(AISLES_URL, timeout=20000)

    # Wait for the navigation menu to load
    await page.wait_for_selector('ul[data-qa="Hdr_tbshmr_ng_prt_lst"]',
    state="attached",      
    timeout=15000)

    # Extract categories and subcategories into a nested dict
    categories = await page.evaluate("""
    () => {
        const result = {};
        document.querySelectorAll('ul[data-qa="Hdr_tbshmr_ng_prt_lst"] > li').forEach(parentLi => {
            const a = parentLi.querySelector('a[role="menuitem"]');
            if (!a) return;
            const parentName = a.textContent.trim();
            const childUl = parentLi.querySelector('ul[data-qa="hdr_tb_shmr_ng_chld2_lst"]');
            if (!childUl) return;
            const subs = Array.from(childUl.querySelectorAll('li a')).map(childA => {
                const name = childA.textContent.trim();
                const href = childA.getAttribute('href');
                const url = new URL(href, location.origin).href;
                return { display_name: name, href: url };
            });
            if (subs.length) {
                result[parentName] = subs;
            }
        });
        return result;
    }
    """)

    # Write out to JSON file
    with open("safeway_categories.json", "w") as f:
        json.dump(categories, f, indent=2)

    print("✅ Categories saved to safeway_categories.json")
    return page

if __name__ == "__main__":
    asyncio.run(
        StealthyFetcher.async_fetch(
            url=AISLES_URL,
            headless=False,
            network_idle=True,
            block_images=False,
            disable_resources=False,
            page_action=extract_categories,
        )
    )
