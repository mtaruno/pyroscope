"""
Generate dense environmental data points with ~5m spacing
This creates a more continuous heatmap visualization
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.environmental import EnvironmentalData
from app.models.scan import ScanRecord
import random
from datetime import datetime, timedelta

def meters_to_degrees(meters):
    """Convert meters to approximate degrees (rough estimate)"""
    # At 34°N latitude, 1 degree ≈ 111km for latitude, ~92km for longitude
    lat_degree = meters / 111000  # meters to latitude degrees
    lng_degree = meters / 92000   # meters to longitude degrees (approximate at 34°N)
    return lat_degree, lng_degree

def generate_grid_points(center_lat, center_lng, grid_size=15, spacing_meters=5):
    """
    Generate a grid of points around a center location
    
    Args:
        center_lat: Center latitude
        center_lng: Center longitude
        grid_size: Number of points in each direction (default 15x15 = 225 points)
        spacing_meters: Spacing between points in meters (default 5m)
    
    Returns:
        List of (lat, lng) tuples
    """
    lat_step, lng_step = meters_to_degrees(spacing_meters)
    points = []
    
    # Generate grid centered on the location
    offset = (grid_size - 1) / 2
    
    for i in range(grid_size):
        for j in range(grid_size):
            lat = center_lat + (i - offset) * lat_step
            lng = center_lng + (j - offset) * lng_step
            points.append((lat, lng))
    
    return points

def generate_dense_environmental_data(db: Session):
    """Generate dense environmental data for existing scans"""
    print("=" * 70)
    print("Generating Dense Environmental Data (5m spacing)")
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
        
        # Generate grid of points (15x15 = 225 points with 5m spacing)
        center_lat = float(scan.latitude) if scan.latitude else 34.2257
        center_lng = float(scan.longitude) if scan.longitude else -117.8512
        
        grid_points = generate_grid_points(center_lat, center_lng, grid_size=15, spacing_meters=5)
        
        # Create environmental data for each point
        base_time = datetime.utcnow() - timedelta(hours=1)
        
        # Get scan's fuel values as baseline
        scan_1h_fuel = float(scan.one_hour_fuel) if scan.one_hour_fuel else 0.025
        scan_10h_fuel = float(scan.ten_hour_fuel) if scan.ten_hour_fuel else 0.100
        scan_100h_fuel = float(scan.hundred_hour_fuel) if scan.hundred_hour_fuel else 0.200
        
        for idx, (lat, lng) in enumerate(grid_points):
            # Add some spatial variation to create interesting heatmap patterns
            # Use position to create gradients
            variation = 1.0 + random.uniform(-0.3, 0.3)
            
            # Create gradients across the area
            x_factor = (idx % 15) / 15  # 0 to 1 from left to right
            y_factor = (idx // 15) / 15  # 0 to 1 from top to bottom
            
            # Plant temperature: warmer in center and bottom
            base_plant_temp = float(scan.avg_plant_temp) if scan.avg_plant_temp else 32.0
            plant_temp = base_plant_temp + random.uniform(-2, 3) * (0.5 + y_factor)
            
            # Air temperature: slightly cooler than plant
            base_air_temp = float(scan.avg_air_temp) if scan.avg_air_temp else 28.0
            air_temp = base_air_temp + random.uniform(-1.5, 2)
            
            # Humidity: lower in warmer areas
            base_humidity = float(scan.avg_humidity) if scan.avg_humidity else 60.0
            humidity = base_humidity + random.uniform(-10, 10) * (1 - y_factor * 0.5)
            humidity = max(30, min(90, humidity))  # Keep in reasonable range
            
            # Fuel loads: vary by position
            fuel_variation = 0.8 + (x_factor * 0.4) + random.uniform(-0.2, 0.2)
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
                measured_at=base_time + timedelta(seconds=idx * 2)
            )
            db.add(point)
            total_points_created += 1
        
        print(f"  Created {len(grid_points)} new points")
    
    db.commit()
    
    print("\n" + "=" * 70)
    print(f"[SUCCESS] Generated {total_points_created} dense data points")
    print(f"Grid: 15x15 points per scan")
    print(f"Spacing: ~5 meters between points")
    print(f"Coverage: ~75m × 75m area per scan")
    print("\nThe heatmaps should now show continuous color gradients!")
    print("=" * 70)

if __name__ == "__main__":
    db = SessionLocal()
    try:
        generate_dense_environmental_data(db)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
