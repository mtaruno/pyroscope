"""
创建示例数据脚本
运行: python create_sample_data.py
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.scan import ScanRecord
from app.models.environmental import EnvironmentalData
from app.models.image import ScanImage
from app.models.robot import RobotStatus
from datetime import datetime, timedelta
import random

def create_sample_scans(db: Session, count: int = 10):
    """创建示例扫描记录"""
    print(f"\nCreating {count} sample scan records...")
    
    # 洛杉矶附近的GPS坐标范围
    base_lat = 34.2257
    base_lng = -117.8512
    
    risk_levels = ['low', 'medium', 'high']
    fuel_loads = ['Low', 'Medium', 'High']
    
    scans = []
    for i in range(count):
        # 随机偏移坐标（在几公里范围内）
        lat_offset = (random.random() - 0.5) * 0.02  # 约2km
        lng_offset = (random.random() - 0.5) * 0.02
        
        risk = random.choice(risk_levels)
        
        # 根据风险等级设置温度
        if risk == 'high':
            avg_plant_temp = random.uniform(32, 36)
            avg_air_temp = random.uniform(28, 32)
        elif risk == 'medium':
            avg_plant_temp = random.uniform(28, 32)
            avg_air_temp = random.uniform(25, 28)
        else:
            avg_plant_temp = random.uniform(24, 28)
            avg_air_temp = random.uniform(22, 26)
        
        scan = ScanRecord(
            zone_id=f"A-{i+1:02d}",
            latitude=base_lat + lat_offset,
            longitude=base_lng + lng_offset,
            gps_accuracy=random.uniform(1.5, 3.5),
            scan_area="50 m × 50 m",
            duration=f"{random.randint(12, 18)} min {random.randint(0, 59)} sec",
            risk_level=risk,
            avg_plant_temp=round(avg_plant_temp, 2),
            avg_air_temp=round(avg_air_temp, 2),
            avg_humidity=round(random.uniform(40, 80), 2),
            wind_speed=round(random.uniform(2, 8), 2),
            temp_diff=round(avg_plant_temp - avg_air_temp, 2),
            fuel_load=fuel_loads[risk_levels.index(risk)],
            fuel_density=round(random.uniform(0.3, 0.9), 2),
            biomass=round(random.uniform(0.5, 2.5), 2),
            robot_id="ROBOT-001",
            completed_at=datetime.now() - timedelta(days=random.randint(0, 30))
        )
        db.add(scan)
        scans.append(scan)
    
    db.commit()
    print(f"[SUCCESS] Created {len(scans)} scan records")
    return scans


def create_environmental_data(db: Session, scans: list):
    """为每个扫描创建环境数据点"""
    print(f"\nCreating environmental data for {len(scans)} scans...")
    
    total_created = 0
    for scan in scans:
        # 每个扫描创建5-10个环境数据点
        num_points = random.randint(5, 10)
        
        for j in range(num_points):
            env_data = EnvironmentalData(
                scan_id=scan.id,
                air_temperature=scan.avg_air_temp + random.uniform(-1, 1),
                air_humidity=scan.avg_humidity + random.uniform(-5, 5),
                wind_speed=scan.wind_speed + random.uniform(-1, 1),
                plant_temperature=scan.avg_plant_temp + random.uniform(-1, 1),
                latitude=scan.latitude + (random.random() - 0.5) * 0.001,
                longitude=scan.longitude + (random.random() - 0.5) * 0.001,
                measured_at=scan.completed_at - timedelta(minutes=random.randint(0, 15))
            )
            db.add(env_data)
            total_created += 1
    
    db.commit()
    print(f"[SUCCESS] Created {total_created} environmental data points")


def create_image_records(db: Session, scans: list):
    """创建图片记录（只存路径，不存实际图片）"""
    print(f"\nCreating image records for {len(scans)} scans...")
    
    image_types = ['thermal', 'visible', 'panorama']
    total_created = 0
    
    for scan in scans:
        # 每个扫描创建2-4张图片
        num_images = random.randint(2, 4)
        
        for j in range(num_images):
            image_type = random.choice(image_types)
            
            # 生成本地路径示例
            date_path = scan.completed_at.strftime("%Y/%m/%d")
            file_path = f"uploads/{image_type}/{date_path}/{image_type}_{scan.id}_{j+1}.jpg"
            
            image = ScanImage(
                scan_id=scan.id,
                image_type=image_type,
                file_path=file_path,
                file_size=random.randint(500000, 3000000),  # 0.5-3MB
                mime_type="image/jpeg",
                width=random.choice([1920, 2048, 3840]),
                height=random.choice([1080, 1536, 2160]),
                latitude=scan.latitude,
                longitude=scan.longitude,
                captured_at=scan.completed_at - timedelta(minutes=random.randint(0, 10)),
                meta_data={
                    "camera_model": random.choice(["FLIR E8", "DJI Mavic 3T", "Canon EOS R5"]),
                    "iso": random.choice([100, 200, 400]),
                    "exposure": f"1/{random.choice([125, 250, 500])}"
                }
            )
            db.add(image)
            total_created += 1
    
    db.commit()
    print(f"[SUCCESS] Created {total_created} image records")


def create_robot_status(db: Session, count: int = 20):
    """创建机器人状态记录"""
    print(f"\nCreating {count} robot status records...")
    
    base_lat = 34.2257
    base_lng = -117.8512
    states = ['idle', 'scanning', 'charging']
    
    for i in range(count):
        status = RobotStatus(
            robot_id="ROBOT-001",
            battery_level=random.randint(20, 100),
            storage_used=round(random.uniform(0, 7), 2),
            storage_total=8.0,
            signal_strength=random.choice(['Excellent', 'Good', 'Fair']),
            operating_state=random.choice(states),
            latitude=base_lat + (random.random() - 0.5) * 0.02,
            longitude=base_lng + (random.random() - 0.5) * 0.02,
            recorded_at=datetime.now() - timedelta(hours=random.randint(0, 48))
        )
        db.add(status)
    
    db.commit()
    print(f"[SUCCESS] Created {count} robot status records")


def main():
    print("=" * 60)
    print("Pyroscope Dashboard - Sample Data Generator")
    print("=" * 60)
    
    # 创建数据库会话
    db = SessionLocal()
    
    try:
        # 检查是否已有数据
        existing_scans = db.query(ScanRecord).count()
        
        if existing_scans > 0:
            print(f"\n[WARNING] Database already has {existing_scans} scan records")
            response = input("Do you want to add more data? (y/n): ")
            if response.lower() != 'y':
                print("Cancelled.")
                return
        
        # 创建示例数据
        scans = create_sample_scans(db, count=10)
        create_environmental_data(db, scans)
        create_image_records(db, scans)
        create_robot_status(db, count=20)
        
        # 显示统计
        print("\n" + "=" * 60)
        print("Sample Data Summary:")
        print("=" * 60)
        print(f"Total Scans: {db.query(ScanRecord).count()}")
        print(f"Total Environmental Data: {db.query(EnvironmentalData).count()}")
        print(f"Total Images: {db.query(ScanImage).count()}")
        print(f"Total Robot Status: {db.query(RobotStatus).count()}")
        print("=" * 60)
        print("\n[SUCCESS] Sample data created successfully!")
        print("\nYou can now:")
        print("1. Start the backend: python run.py")
        print("2. Visit: http://localhost:8000/docs")
        print("3. Test API: GET /api/scans")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
