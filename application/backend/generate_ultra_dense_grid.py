"""
Generate precise 20x20 grid with 2.5m spacing within 50m×50m boundary
Total: 400 points per scan
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.environmental import EnvironmentalData
from app.models.scan import ScanRecord
import random
from datetime import datetime, timedelta

def generate_precise_grid_points(center_lat, center_lng, grid_size=20, spacing_meters=2.5):
    """
    Generate a precise 20x20 grid with 2.5m spacing
    Total coverage: 47.5m × 47.5m (within 50m boundary)
    
    Args:
        center_lat: Center latitude
        center_lng: Center longitude
        grid_size: 20 (20x20 = 400 points)
        spacing_meters: 2.5m between adjacent points
    
    Returns:
        List of (lat, lng) tuples
    """
    # Convert meters to degrees
    lat_step = spacing_meters / 111000  # 2.5m in latitude degrees
    lng_step = spacing_meters / (111000 * 0.8290)  # 2.5m at ~34°N (cos(34°) ≈ 0.829)
    
    points = []
    
    # Calculate grid centered on location
    # 20 points with 2.5m spacing = 47.5m total (within 50m)
    offset = (grid_size - 1) / 2  # 9.5 for 20x20 grid
    
    for i in range(grid_size):
        for j in range(grid_size):
            # Calculate position relative to center
            lat_offset = (i - offset) * lat_step
            lng_offset = (j - offset) * lng_step
            
            lat = center_lat + lat_offset
            lng = center_lng + lng_offset
            
            points.append((lat, lng))
    
    return points

def generate_ultra_dense_data(db: Session):
    """Generate 20x20 grid (400 points) with 2.5m spacing for each scan"""
    print("=" * 70)
    print("Generating Ultra-Dense Grid Data")
    print("Grid: 20×20 = 400 points per scan")
    print("Spacing: 2.5 meters")
    print("Coverage: 47.5m × 47.5m (within 50m boundary)")
    print("=" * 70)
    
    # Get all scans
    scans = db.query(ScanRecord).all()
    print(f"\nFound {len(scans)} scans")
    
    total_points_created = 0
    
    for scan in scans:
        print(f"\n[Processing] Scan ID {scan.id} - Zone {scan.zone_id}")
        
        # Delete existing environmental data for this scan
        deleted = db.query(EnvironmentalData).filter(
            EnvironmentalData.scan_id == scan.id
        ).delete()
        print(f"  Deleted {deleted} old points")
        
        # Generate precise 20x20 grid
        center_lat = float(scan.latitude) if scan.latitude else 34.2257
        center_lng = float(scan.longitude) if scan.longitude else -117.8512
        
        grid_points = generate_precise_grid_points(center_lat, center_lng, grid_size=20, spacing_meters=2.5)
        
        # Create environmental data for each point
        base_time = datetime.now() - timedelta(hours=1)
        
        # Get scan's baseline values
        scan_1h_fuel = float(scan.one_hour_fuel) if scan.one_hour_fuel else 0.025
        scan_10h_fuel = float(scan.ten_hour_fuel) if scan.ten_hour_fuel else 0.100
        scan_100h_fuel = float(scan.hundred_hour_fuel) if scan.hundred_hour_fuel else 0.200
        base_plant_temp = float(scan.avg_plant_temp) if scan.avg_plant_temp else 32.0
        base_air_temp = float(scan.avg_air_temp) if scan.avg_air_temp else 28.0
        base_humidity = float(scan.avg_humidity) if scan.avg_humidity else 60.0
        
        for idx, (lat, lng) in enumerate(grid_points):
            # Calculate grid position (0-19 for both x and y)
            x_pos = idx % 20
            y_pos = idx // 20
            
            # Create smooth gradients across the area for natural variation
            # Normalize to 0-1
            x_norm = x_pos / 19.0
            y_norm = y_pos / 19.0
            
            # Use sine waves for smooth variation patterns
            import math
            wave1 = math.sin(x_norm * math.pi * 2) * 0.3
            wave2 = math.cos(y_norm * math.pi * 2) * 0.3
            combined_wave = (wave1 + wave2) / 2
            
            # Plant temperature: smooth gradient pattern
            plant_temp = base_plant_temp + combined_wave * 5 + random.uniform(-1, 1)
            plant_temp = max(20, min(45, plant_temp))
            
            # Air temperature: similar but slightly lower
            air_temp = base_air_temp + combined_wave * 3 + random.uniform(-0.8, 0.8)
            air_temp = max(18, min(40, air_temp))
            
            # Humidity: inverse relationship with temperature
            humidity = base_humidity - combined_wave * 15 + random.uniform(-5, 5)
            humidity = max(30, min(90, humidity))
            
            # Fuel loads: smooth variation
            fuel_variation = 1.0 + combined_wave * 0.4 + random.uniform(-0.1, 0.1)
            one_hour_fuel = scan_1h_fuel * fuel_variation
            ten_hour_fuel = scan_10h_fuel * fuel_variation
            hundred_hour_fuel = scan_100h_fuel * fuel_variation
            
            point = EnvironmentalData(
                scan_id=scan.id,
                latitude=lat,
                longitude=lng,
                air_temperature=round(air_temp, 2),
                air_humidity=round(humidity, 2),
                wind_speed=round(random.uniform(0.5, 3.5), 2),
                plant_temperature=round(plant_temp, 2),
                one_hour_fuel=round(one_hour_fuel, 4),
                ten_hour_fuel=round(ten_hour_fuel, 4),
                hundred_hour_fuel=round(hundred_hour_fuel, 4),
                measured_at=base_time + timedelta(seconds=idx)
            )
            db.add(point)
            total_points_created += 1
        
        print(f"  Created {len(grid_points)} new points (20×20 grid)")
    
    db.commit()
    
    print("\n" + "=" * 70)
    print(f"[SUCCESS] Generated {total_points_created} ultra-dense points")
    print(f"\nConfiguration:")
    print(f"  Grid Size: 20 × 20 = 400 points per scan")
    print(f"  Spacing: 2.5 meters")
    print(f"  Coverage: 47.5m × 47.5m")
    print(f"  Boundary: Within 50m × 50m ✓")
    print(f"\nData Pattern:")
    print(f"  - Smooth sine wave gradients for natural variation")
    print(f"  - Temperature, humidity, and fuel all vary smoothly")
    print(f"  - No hard boundaries or artificial patterns")
    print("\nHeatmaps should now show perfectly smooth gradients!")
    print("=" * 70)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        generate_ultra_dense_data(db)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
