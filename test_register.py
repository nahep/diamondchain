"""
Quick smoke test — run this while backend.py is running.
  python test_register.py
"""
import requests
import json

BASE = "http://localhost:5000"

# 1. Register a diamond
payload = {
    "name":         "Round Brilliant · 1.24ct",
    "origin":       "Botswana, Jwaneng",
    "country_code": "BW",
    "grade":        "D / VVS1 / Excellent",
    "cert":         "GIA 6482910337",
    "miner":        "Debswana",
    "weight_ct":    1.24,
    "custody": [
        {
            "event":    "Extracted & registered",
            "location": "Jwaneng Mine, Botswana",
            "actor":    "Debswana",
            "status":   "done",
        },
        {
            "event":    "Cut & polished",
            "location": "Surat, India · Kiran Gems",
            "actor":    "Kiran Gems",
            "status":   "done",
        },
        {
            "event":    "GIA certified",
            "location": "Antwerp, Belgium",
            "actor":    "GIA Lab",
            "status":   "done",
        },
        {
            "event":    "With retailer",
            "location": "Amsterdam · Gassan Diamonds",
            "actor":    "Gassan Diamonds",
            "status":   "active",
        },
        {
            "event":    "Consumer purchase",
            "location": "",
            "actor":    "",
            "status":   "pending",
        },
    ]
}

print("Registering diamond...")
r = requests.post(f"{BASE}/register", json=payload)
r.raise_for_status()
result = r.json()

diamond_id = result["diamond_id"]
print(f"\nDiamond ID:    {diamond_id}")
print(f"TX Signature:  {result['tx_signature']}")
print(f"Verify URL:    {result['verify_url']}")

# 2. Fetch passport
print("\nFetching passport...")
r2 = requests.get(f"{BASE}/verify/{diamond_id}")
passport = r2.json()
print(json.dumps(passport, indent=2))

# 3. Save QR
print("\nDownloading QR...")
r3 = requests.get(f"{BASE}/qr/{diamond_id}")
fname = f"qr_{diamond_id}.png"
with open(fname, "wb") as f:
    f.write(r3.content)
print(f"QR saved to {fname}")
