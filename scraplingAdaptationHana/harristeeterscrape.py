from playwright.sync_api import sync_playwright
import json
import os

CACHE_FILE = "scraplingAdaptationHana/upc_data.json"
UPC_DATA = None
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        try:
            UPC_DATA = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Cache file exists but is invalid or empty. Starting fresh.")
            UPC_DATA = {}
else: UPC_DATA = {}

def upc_to_gtin13(upc12):
    # drop last digit, pad to 13
    core = upc12[:-1]
    return core.zfill(13)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False)     # headless=False lets you log in / interact
    ctx     = browser.new_context()
    page    = ctx.new_page()

    # 1) Manually log in / navigate once:
    page.goto("https://www.harristeeter.com")
    # — manually search any product, accept cookies, etc —
    input("✅  Now that you’re logged in and have a working session, press ENTER to continue…")

    # 2) Get hold of that magical x-laf-object header
    #    (HT actually puts it in localStorage, or you can read from a real network request)
    laf_object = page.evaluate("() => window.localStorage.getItem('lafObject')")  
    # (Or scrape it from network via `page.on('request')`, if they store it elsewhere.)

    results = []
    for upc in UPC_DATA.keys():
        gtin13 = upc_to_gtin13(upc)
        url = (
            "https://www.harristeeter.com/atlas/v1/product/v2/products"
            f"?filter.gtin13s={gtin13}"
            "&filter.verified=true"
            "&projections=items.full,offers.compact,nutrition.label,variantGroupings.compact"
        )

        # 3) Fire the same XHR that the page would
        response = ctx.request.get(
            url,
            headers={
                "x-laf-object": laf_object,
                "Accept": "application/json, text/plain, */*",
            }
        )
        data = response.json()
        prod = data["data"]["products"][0]
        results.append({
            "upc": upc,
            "gtin13":   prod["gtin13"],
            "price":    prod["offers"]["price"]["price"],
            "size":     prod["customerFacingSize"],
            "desc":     prod["description"],
        })

    print(json.dumps(results, indent=2))
    browser.close()
