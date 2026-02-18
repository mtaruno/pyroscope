"""
Update existing environmental_data with fuel estimation values
This simulates what would happen when robot uploads point-by-point data with fuel
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.environmental import EnvironmentalData
from app.models.scan import ScanRecord
import random

def update_environmental_with_fuel(db: Session):
    """Add fuel estimation data to existing environmental_data records"""
    print("=" * 70)
    print("Updating Environmental Data with Fuel Estimates")
    print("=" * 70)
    
    # Get all environmental data
    env_data = db.query(EnvironmentalData).all()
    print(f"\nFound {len(env_data)} environmental data points")
    
    updated = 0
    for point in env_data:
        # Get the scan's fuel data as reference
        scan = db.query(ScanRecord).filter(ScanRecord.id == point.scan_id).first()
        
        if scan and scan.one_hour_fuel:
            # Add some variation around the scan's average fuel values
            # Simulating per-point fuel estimation
            variation = random.uniform(0.8, 1.2)
            
            point.one_hour_fuel = float(scan.one_hour_fuel) * variation if scan.one_hour_fuel else random.uniform(0.01, 0.05)
            point.ten_hour_fuel = float(scan.ten_hour_fuel) * variation if scan.ten_hour_fuel else random.uniform(0.05, 0.15)
            point.hundred_hour_fuel = float(scan.hundred_hour_fuel) * variation if scan.hundred_hour_fuel else random.uniform(0.05, 0.30)
            
            updated += 1
        else:
            # No scan fuel data, generate random values
            point.one_hour_fuel = random.uniform(0.01, 0.05)
            point.ten_hour_fuel = random.uniform(0.05, 0.15)
            point.hundred_hour_fuel = random.uniform(0.05, 0.30)
            updated += 1
    
    db.commit()
    
    print(f"\n[SUCCESS] Updated {updated} points with fuel estimation data")
    print("\nSample data (first 5 points):")
    print("-" * 70)
    
    sample_points = db.query(EnvironmentalData).limit(5).all()
    for point in sample_points:
        print(f"Point {point.id}:")
        print(f"  Location: ({point.latitude}, {point.longitude})")
        print(f"  Plant Temp: {point.plant_temperature}°C")
        print(f"  Air Humidity: {point.air_humidity}%")
        print(f"  1h Fuel: {point.one_hour_fuel:.4f} tons/acre")
        print(f"  10h Fuel: {point.ten_hour_fuel:.4f} tons/acre")
        print(f"  100h Fuel: {point.hundred_hour_fuel:.4f} tons/acre")
        print()
    
    print("=" * 70)
    print("[COMPLETE] Environmental data updated with fuel estimates")
    print("\nYou can now test the heatmap:")
    print("1. Visit http://localhost:5173")
    print("2. Click on any scan marker")
    print("3. View heatmaps on the right panel")
    print("=" * 70)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        update_environmental_with_fuel(db)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
