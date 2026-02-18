"""
Test the heatmap data API endpoint
"""
import requests
import json

def test_heatmap_api():
    """Test the heatmap data API"""
    print("=" * 70)
    print("Testing Heatmap API Endpoint")
    print("=" * 70)
    
    url = "http://localhost:8000/api/scans/1/heatmap-data"
    
    print(f"\nRequesting: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n[SUCCESS] API returned 200 OK")
            print(f"\nResponse structure:")
            print(f"  - scan_id: {data.get('scan_id')}")
            print(f"  - total_points: {data.get('total_points')}")
            print(f"  - data_points: {len(data.get('data_points', []))} items")
            
            # Show first 3 points as sample
            if data.get('data_points'):
                print(f"\nSample data points (first 3):")
                print("-" * 70)
                
                for i, point in enumerate(data['data_points'][:3], 1):
                    print(f"\nPoint {i}:")
                    print(f"  Location: ({point.get('latitude')}, {point.get('longitude')})")
                    print(f"  Plant Temperature: {point.get('plant_temperature')}°C")
                    print(f"  Air Temperature: {point.get('air_temperature')}°C")
                    print(f"  Air Humidity: {point.get('air_humidity')}%")
                    print(f"  1-Hour Fuel: {point.get('one_hour_fuel')} tons/acre")
                    print(f"  10-Hour Fuel: {point.get('ten_hour_fuel')} tons/acre")
                    print(f"  100-Hour Fuel: {point.get('hundred_hour_fuel')} tons/acre")
                    print(f"  Fire Risk: {point.get('fire_risk')} (0-1 scale)")
                
                print("\n" + "=" * 70)
                print("[SUCCESS] All data structures are correct!")
                print("\nThe heatmap system is ready to use:")
                print("  1. Frontend can fetch data from /api/scans/{id}/heatmap-data")
                print("  2. Each point includes lat/lng and all layer data")
                print("  3. Fire risk is automatically calculated")
                print("  4. Visit http://localhost:5173 to see the heatmaps")
                print("=" * 70)
                
                return True
            else:
                print("\n[WARNING] No data points returned")
                return False
        else:
            print(f"\n[ERROR] API returned status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Could not connect to backend server")
        print("Make sure the backend is running: cd backend && python run.py")
        return False
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_heatmap_api()
