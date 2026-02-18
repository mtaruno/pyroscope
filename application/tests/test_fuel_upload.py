"""
测试燃料估算功能
上传 test 文件夹中的图片并获取燃料估算结果
"""
import requests
import os
import time
from pathlib import Path

API_URL = "http://localhost:8000/api"

def test_fuel_estimation():
    print("=" * 70)
    print("Fuel Estimation Test")
    print("=" * 70)
    
    # 1. 创建测试扫描记录
    print("\n[Step 1] Creating test scan record...")
    scan_data = {
        "zone_id": "TEST-01",
        "latitude": 34.2257,
        "longitude": -117.8512,
        "avg_air_temp": 29.0,
        "robot_id": "ROBOT-TEST"
    }
    
    try:
        response = requests.post(f"{API_URL}/scans", json=scan_data, timeout=10)
        response.raise_for_status()
        scan_id = response.json()["scan_id"]
        print(f"[SUCCESS] Scan created with ID: {scan_id}")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to create scan: {e}")
        print("\nIs the backend running? Try: python backend/run.py")
        return False
    
    # 2. 获取测试图片
    test_dir = Path("test")
    images = list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.jpeg")) + list(test_dir.glob("*.png"))
    
    if not images:
        print("\n[ERROR] No images found in test/ folder")
        return False
    
    print(f"\n[Step 2] Found {len(images)} test image(s)")
    
    # 3. 上传每张图片并估算燃料
    results = []
    for i, image_path in enumerate(images, 1):
        print(f"\n--- Testing Image {i}/{len(images)}: {image_path.name} ---")
        print(f"File size: {image_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        try:
            with open(image_path, 'rb') as f:
                files = {'file': (image_path.name, f, 'image/jpeg')}
                data = {
                    'scan_id': scan_id,
                    'image_type': 'visible',
                    'estimate_fuel': 'true'
                }
                
                print("[Uploading] Sending image to API...")
                print("[Processing] Calling Wildlands AI (this may take 30-60 seconds)...")
                start_time = time.time()
                
                response = requests.post(
                    f"{API_URL}/images/upload",
                    files=files,
                    data=data,
                    timeout=120  # 2分钟超时
                )
                
                elapsed = time.time() - start_time
                print(f"[Completed] Processing took {elapsed:.1f} seconds")
                
                response.raise_for_status()
                result = response.json()
                
                # 显示结果
                if 'fuel_estimation' in result and result['fuel_estimation']:
                    fuel = result['fuel_estimation']
                    print("\n" + "=" * 50)
                    print(f"[SUCCESS] Fuel Estimation Results for {image_path.name}")
                    print("=" * 50)
                    print(f"  Total Fuel Load:     {fuel['total_fuel_load']:.4f} tons/acre")
                    print(f"  1-Hour Fuel:         {fuel['one_hour_fuel']:.4f} tons/acre")
                    print(f"  10-Hour Fuel:        {fuel['ten_hour_fuel']:.4f} tons/acre")
                    print(f"  100-Hour Fuel:       {fuel['hundred_hour_fuel']:.4f} tons/acre")
                    print(f"  Pine Cone Count:     {fuel['pine_cone_count']}")
                    print("=" * 50)
                    
                    results.append({
                        'image': image_path.name,
                        'success': True,
                        'fuel_estimation': fuel
                    })
                else:
                    print(f"\n[WARNING] No fuel estimation data returned for {image_path.name}")
                    print("Response:", result)
                    results.append({
                        'image': image_path.name,
                        'success': False,
                        'message': 'No fuel estimation data'
                    })
                
        except requests.exceptions.Timeout:
            print(f"\n[ERROR] Request timeout for {image_path.name}")
            print("The Wildlands AI service might be slow. Try increasing timeout.")
            results.append({
                'image': image_path.name,
                'success': False,
                'message': 'Timeout'
            })
        except requests.exceptions.RequestException as e:
            print(f"\n[ERROR] Failed to upload {image_path.name}: {e}")
            results.append({
                'image': image_path.name,
                'success': False,
                'message': str(e)
            })
    
    # 4. 显示汇总
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Total images tested: {len(images)}")
    print(f"Successful: {sum(1 for r in results if r['success'])}")
    print(f"Failed: {sum(1 for r in results if not r['success'])}")
    
    # 5. 查询扫描详情
    print(f"\n[Step 3] Fetching scan details (ID: {scan_id})...")
    try:
        response = requests.get(f"{API_URL}/scans/{scan_id}", timeout=10)
        response.raise_for_status()
        scan_detail = response.json()
        
        print("\n[Scan Record Updated]")
        print(f"  Zone ID: {scan_detail.get('zone_id')}")
        print(f"  Total Fuel Load: {scan_detail.get('fuel_load', 'N/A')} tons/acre")
        print(f"  Images attached: {len(scan_detail.get('images', []))}")
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch scan details: {e}")
    
    print("\n" + "=" * 70)
    print("[TEST COMPLETE]")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    success = test_fuel_estimation()
    exit(0 if success else 1)
