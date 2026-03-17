"""
Update scan_records with aggregate values from environmental_data or scan_waypoint_samples.
This calculates avg_plant_temp, avg_air_temp, avg_humidity, temp_diff, and legacy fuel_load.
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.scan import ScanRecord
from app.models.environmental import EnvironmentalData
from app.models.waypoint_sample import ScanWaypointSample
from app.services.scan_aggregate_service import ScanAggregateService

def update_scan_aggregates(db: Session):
    """Calculate and update aggregate values for all scans"""
    print("=" * 70)
    print("Updating Scan Aggregate Values")
    print("=" * 70)
    
    scans = db.query(ScanRecord).all()
    print(f"\nFound {len(scans)} scans to update")
    
    updated = 0
    for scan in scans:
        env_data = db.query(EnvironmentalData).filter(
            EnvironmentalData.scan_id == scan.id
        ).all()
        waypoint_data = db.query(ScanWaypointSample).filter(
            ScanWaypointSample.scan_id == scan.id
        ).all()

        if not env_data and not waypoint_data:
            print(f"\n[SKIP] Scan {scan.id} ({scan.zone_id}) - No environmental or waypoint data")
            continue

        ScanAggregateService.refresh_scan_aggregates(db, scan.id, commit=False)

        # Calculate total fuel load (sum of all three fuel types, then average)
        total_fuels = []
        for d in env_data:
            if d.one_hour_fuel and d.ten_hour_fuel and d.hundred_hour_fuel:
                total = float(d.one_hour_fuel) + float(d.ten_hour_fuel) + float(d.hundred_hour_fuel)
                total_fuels.append(total)

        if total_fuels:
            scan.fuel_load = round(sum(total_fuels) / len(total_fuels), 4)

        updated += 1
        point_count = len(env_data) if env_data else len(waypoint_data)
        source = "environmental_data" if env_data else "scan_waypoint_samples"

        print(f"\n[UPDATE] Scan {scan.id} ({scan.zone_id}):")
        print(f"  Source: {source}")
        print(f"  Points: {point_count}")
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
