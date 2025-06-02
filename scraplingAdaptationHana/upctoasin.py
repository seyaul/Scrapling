import requests
import pandas as pd
import json
import traceback
import time
import threading
import random

SRC_DATA = "scraplingAdaptationHana/source_prices.xlsx"
OUT_DATA = "session_results_upc_to_asin.json"

pause_event = threading.Event()

def toggle_pause():
    while True:
        input(">> Press Enter to toggle pause/resume\n")
        if pause_event.is_set():
            print("Resuming...")
            pause_event.clear()
        else:
            print("Paused. Press Enter again to resume.")
            pause_event.set()

def get_asin_from_upc(upc):
    url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={upc}"
    try:
        response = requests.get(url)
        print(f"Request Status for {upc}: {response.status_code}")
        if response.status_code != 200:
            print(f"Non-200 response for {upc}: {response.text}")
            return None

        data = response.json()
        for item in data.get('items', []):
            if 'asin' in item:
                print(f"Found ASIN for UPC {upc}: {item['asin']}")
                return item['asin']
        print(f"No ASIN found in response for UPC {upc}: {data}")
    except Exception as e:
        print(f"Exception occurred for UPC {upc}: {e}")
        traceback.print_exc()
    return "null, manual search required"

def get_asin_from_upcs(upc_list):
    results = {}
    for upc in upc_list:
        while pause_event.is_set():
            print("Paused. Waiting to resume...")
            time.sleep(4)
        asin = get_asin_from_upc(upc)
        results[upc] = asin if asin else None
        time.sleep(random.uniform(3,7))  # Respect rate limits
    with open(OUT_DATA, 'w') as f:
        json.dump(results, f, indent=2)
    return results

if __name__ == "__main__":
    read_file = pd.read_excel(SRC_DATA)
    upc_list = read_file['UPC'].dropna().astype(str).tolist()
    upc_list_b1 = upc_list[:50]

    # Start thread to listen for Enter key
    listener_thread = threading.Thread(target=toggle_pause, daemon=True)
    listener_thread.start()

    asin_results = get_asin_from_upcs(upc_list_b1)
    print("Final Results:")
    print(asin_results)
    print(f"Results saved to {OUT_DATA}")