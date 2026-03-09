"""
Simple script to test image upload API
Usage: python upload_test.py
"""
import requests
import os

# API endpoint
url = "http://localhost:8000/api/images/upload"

# Get the test image path
script_dir = os.path.dirname(os.path.abspath(__file__))
image_path = os.path.join(script_dir, "04.HEIC")

if not os.path.exists(image_path):
    print(f"[ERROR] Image not found at {image_path}")
    exit(1)

# Prepare the multipart form data
files = {
    'file': ('04.HEIC', open(image_path, 'rb'), 'image/jpeg')
}
data = {
    'scan_id': '2',
    'image_type': 'visible'  # Valid types: thermal, visible, panorama, detail
}

print(f"[INFO] Uploading image: {image_path}")
print(f"       scan_id: 3")
print(f"       image_type: visible")
print()

try:
    response = requests.post(url, files=files, data=data)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(response.json())
    
    # 2xx status codes indicate success (200 OK, 201 Created, etc.)
    if 200 <= response.status_code < 300:
        print("\n[SUCCESS] Upload successful!")
        result = response.json()
        if 'fuel_estimation' in result:
            print("\n=== Fuel Estimation Results ===")
            fuel = result['fuel_estimation']
            print(f"Total Fuel Load: {fuel.get('total_fuel_load', 'N/A')} tons/acre")
            print(f"1-Hour Fuel: {fuel.get('one_hour_fuel', 'N/A')} tons/acre")
            print(f"10-Hour Fuel: {fuel.get('ten_hour_fuel', 'N/A')} tons/acre")
            print(f"100-Hour Fuel: {fuel.get('hundred_hour_fuel', 'N/A')} tons/acre")
            print(f"Pine Cone Count: {fuel.get('pine_cone_count', 'N/A')}")
    else:
        print("\n[FAILED] Upload failed!")
        
except requests.exceptions.ConnectionError:
    print("[ERROR] Cannot connect to backend at http://localhost:8000")
    print("        Make sure the backend server is running!")
except Exception as e:
    print(f"[ERROR] {e}")
