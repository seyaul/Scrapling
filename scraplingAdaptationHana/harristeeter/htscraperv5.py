import uuid, json, requests

BASE      = "https://mobile.kroger.com"
FACILITY  = "09700352"        # store / pickup location
BANNER    = "HarrisTeeter"
SKU_BATCH = ["000000000283", "0001110181899"]

UA = ("krogerco/83.0/Android "
      "Mozilla/5.0 (Linux; Android 14; Pixel 7a)")

# ---------- 1) bootstrap ----------
boot_headers = {
    "accept": "application/json",
    "accept-language": "en-US",
    "user-agent": UA,
    "x-kroger-tenant": "harristeeter",
    "x-kroger-channel": "MOBILE;ANDROID",
    "x-device-type": "Android Phone XXXHDPI",
    "x-device-os-version": "14",
    "x-correlation-id": str(uuid.uuid4()),
}

boot_payload = {
    "filter.banner": BANNER,
    "filter.locationId": FACILITY
}


# ---------- 2) product info ----------
prod_headers = boot_headers | {
    "x-facility-id": FACILITY,
    "x-modality": json.dumps({"type":"PICKUP","locationId":FACILITY}),
    "x-modality-type": "PICKUP",
    "x-correlation-id": str(uuid.uuid4())  # fresh for each call
}

url = (f"{BASE}/mobileproduct/api/v3/product/info"
       f"?banner={BANNER}&include=sizes&unverified=false")

resp = requests.post(
    url,
    headers=prod_headers,
    data=json.dumps(SKU_BATCH),
    timeout=12
)

print(resp.status_code)
print(resp.json()[:1])  # first product