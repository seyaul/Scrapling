import requests
import pandas as pd
import os, json

CACHE_FILE = "scraplingAdaptationHana/upc_data.json"
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        try:
            upc_data = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Cache file exists but is invalid or empty. Starting fresh.")
            upc_data = {}
else: upc_data = {}


def extract_upcs(file_path):
    # Automatically detect file type
    if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
        df = pd.read_excel(file_path)
    elif file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        raise ValueError("Unsupported file format. Please use .csv or .xlsx")

    # Check if UPC column exists (case insensitive)
    upc_col = next((col for col in df.columns if col.strip().lower() == "upc"), None)
    if not upc_col:
        raise KeyError("No 'UPC' column found in the dataset.")

    # Drop missing values and return as list of strings
    upcs = df[upc_col].dropna().astype(str).tolist()
    return upcs

# Example usage
file_path = "scraplingAdaptationHana/source_prices.xlsx"

tot_not_found = 0
def fetch_openfoodfacts_by_upc(upc):
    global tot_not_found
    global upc_data
    url = f"https://world.openfoodfacts.org/api/v0/product/{upc}.json"
    response = requests.get(url, timeout=10)
    data = response.json()
    #print(f"Response: {data}")
    if data.get("status") == 1 and "product" in data:
            product = data["product"]
            # print(product.get("sources"))
            # print(product.get("product_name"))
            if upc in upc_data:
                print(f"⚠️ Skipping cached upc: {upc}.")
            else:
                upc_data[product.get("code")] = [product.get("product_name"), product.get("brands"), product.get("quantity")]
            # return data["product"]
            return product
    else:
        print(f"⚠️ No product found for UPC {upc}")
        tot_not_found += 1
        upc_data[upc] = None
        return None
    # if data.get("status") == 1:
        
    #     return {
    #         "UPC": upc,
    #         # "Product Name": product.get("product_name"),
    #         # "Brand": product.get("brands"),
    #         # "Quantity": product.get("quantity"),
    #         # "Categories": product.get("categories"),
    #         # "Ingredients Text": product.get("ingredients_text"),
    #         # "Nutriscore Grade": product.get("nutriscore_grade"),
    #         # "Image URL": product.get("image_url"),
    #     }
    # else:
    #     return {"UPC": upc, "Error": "Not Found"}

# Example UPCs
upcs = extract_upcs(file_path)  # Use the extracted UPCs from the file


results = []
row_num=1

#191, 296, 449
for upc in range(400, 465):
    print(f"🔍 Fetching UPC {upcs[upc]}")
    results.append(fetch_openfoodfacts_by_upc(upcs[upc]))
    print(row_num)
    row_num+=1
print(f"Total not found: {tot_not_found}")
#results = [fetch_openfoodfacts_by_upc(upc) for upc in upcs]

print(upc_data)

with open(CACHE_FILE, "w") as f:
    json.dump(upc_data, f, indent = 2)


