"""
Update scan_records with aggregate values from environmental_data
This calculates avg_plant_temp, avg_air_temp, avg_humidity, and total fuel_load
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SessionLocal
from app.models.scan import ScanRecord
from app.models.environmental import EnvironmentalData

def update_scan_aggregates(db: Session):
    """Calculate and update aggregate values for all scans"""
    print("=" * 70)
    print("Updating Scan Aggregate Values")
    print("=" * 70)
    
    scans = db.query(ScanRecord).all()
    print(f"\nFound {len(scans)} scans to update")
    
    updated = 0
    for scan in scans:
        # Get all environmental data for this scan
        env_data = db.query(EnvironmentalData).filter(
            EnvironmentalData.scan_id == scan.id
        ).all()
        
        if not env_data:
            print(f"\n[SKIP] Scan {scan.id} ({scan.zone_id}) - No environmental data")
            continue
        
        # Calculate averages
        plant_temps = [float(d.plant_temperature) for d in env_data if d.plant_temperature]
        air_temps = [float(d.air_temperature) for d in env_data if d.air_temperature]
        humidities = [float(d.air_humidity) for d in env_data if d.air_humidity]
        
        # Calculate total fuel load (sum of all three fuel types, then average)
        total_fuels = []
        for d in env_data:
            if d.one_hour_fuel and d.ten_hour_fuel and d.hundred_hour_fuel:
                total = float(d.one_hour_fuel) + float(d.ten_hour_fuel) + float(d.hundred_hour_fuel)
                total_fuels.append(total)
        
        # Update scan record
        if plant_temps:
            scan.avg_plant_temp = round(sum(plant_temps) / len(plant_temps), 2)
        
        if air_temps:
            scan.avg_air_temp = round(sum(air_temps) / len(air_temps), 2)
        
        if humidities:
            scan.avg_humidity = round(sum(humidities) / len(humidities), 2)
        
        if total_fuels:
            scan.fuel_load = round(sum(total_fuels) / len(total_fuels), 4)
        
        # Calculate temp_diff if both temps available
        if scan.avg_plant_temp and scan.avg_air_temp:
            scan.temp_diff = round(scan.avg_plant_temp - scan.avg_air_temp, 2)
        
        updated += 1
        
        print(f"\n[UPDATE] Scan {scan.id} ({scan.zone_id}):")
        print(f"  Points: {len(env_data)}")
        print(f"  Avg Ground Temp: {scan.avg_plant_temp}°C")
        print(f"  Avg Air Temp: {scan.avg_air_temp}°C")
        print(f"  Avg Humidity: {scan.avg_humidity}%")
        print(f"  Total Fuel Load: {scan.fuel_load} tons/acre")
        print(f"  Temp Diff: {scan.temp_diff}°C")
    
    db.commit()
    
    print("\n" + "=" * 70)
    print(f"[SUCCESS] Updated {updated} scans with aggregate values")
    print("\nThe Scan Data Log should now display:")
    print("  - Avg Ground Temp (°C)")
    print("  - Total Fuel Load (tons/acre)")
    print("=" * 70)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        update_scan_aggregates(db)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
