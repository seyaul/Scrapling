import requests
import uuid
import json

# Define target location
location_id = "09700253"
banner = "HarrisTeeter"

# Endpoint
url = "https://mobile.kroger.com/mobileproduct/api/v4/bootstrap"

# Payload for the POST request
payload = {
    "filter.banner": banner,
    "filter.locationId": location_id,
    "device": {
        "os": "iOS",
        "osVersion": "16.0.2",
        "deviceModel": "iPhone15,3",
        "appVersion": "60.1.1",
        "deviceId": str(uuid.uuid4())
    }
}

# Headers — feel free to tweak the User-Agent for Android if needed
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Kroger/60.1.1 (iPhone; iOS 16.0.2; Scale/3.00)",
    "x-kroger-channel": "MOBILE_IOS"
}

# Make the request
response = requests.post(url, json=payload, headers=headers)

# Handle response
if response.status_code == 200:
    data = response.json()
    print("✅ appSessionScopedToken:\n", data["appSessionScopedToken"])
    print("\n✅ x-laf-object:\n", json.dumps(data["lafObject"], indent=2))
else:
    print(f"❌ Error {response.status_code}: {response.text}")
