import asyncio
import random
from scrapling.fetchers import StealthyFetcher
import httpx
import asyncio

SAF_BREAD = "https://www.safeway.com/aisle-vs/bread-bakery/breads.html"

async def extract_safeway_cookies(page):
    jar = {}
    cookies = await page.context.cookies()
    for c in cookies:
        if "safeway.com" in c["domain"]:
            jar[c["name"]] = c["value"]
    return jar

async def safeway_page_action(page):
    # Step 1: Go to Safeway homepage
    widget_id = None

    # hook into every outgoing request
    page.on("request", lambda request: _catch_widget_id(request))

    def _catch_widget_id(request):
        url = request.url
        if "wcax/pathway/search" in url:
            # parse the URL and extract widget-id
            params = dict(x.split("=",1) for x in url.split("?")[1].split("&"))
            nonlocal widget_id
            widget_id = params.get("widget-id")
            print(f"🔍 Found widget-id: {widget_id} in request to {url}")

    # navigate & store‐select…
    await page.goto(SAF_BREAD, timeout=20000)
    input("🛒 select store and hit Enter…")

    # if not widget_id:
    #     raise RuntimeError("Could not auto-discover widget-id")
    print("🔖 Discovered widget-id:", widget_id)

    cookies = await extract_safeway_cookies(page)
    print(f"🍪 Extracted {len(cookies)} Safeway cookies.")

    data = await fetch_safeway_widget(cookies, widget_id)

    for item in data.get("response", {}).get("docs", []):
        print(item["name"], "-", item.get("price"))
    
    return page

async def fetch_safeway_widget(cookie_jar, widget_id, store_id="2912", start=0):
    headers = {
        "accept": "application/json, text/plain, */*",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/136.0.0.0 Safari/537.36",
        "referer": "https://www.safeway.com/",
    }

    url = (
        "https://www.safeway.com/abs/pub/xapi/wcax/pathway/search"
        f"?request-id=staticrequest123"
        f"&url=https://www.safeway.com"
        f"&rows=30&start={start}"
        f"&channel=instore&storeid={store_id}"
        f"&widget-id={widget_id}"
        "&dvid=web-4.1search&banner=safeway&facet=false"
    )

    with httpx.Client(headers=headers, cookies=cookie_jar, timeout=20) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()

if __name__ == "__main__":
    asyncio.run(
        StealthyFetcher.async_fetch(
            url=SAF_BREAD,
            headless=False,
            network_idle=True,
            block_images=False,
            disable_resources=False,
            page_action=safeway_page_action,
        )
    )
