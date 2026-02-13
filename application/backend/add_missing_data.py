"""
为已有的扫描记录添加环境数据和图片记录
运行: python add_missing_data.py
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.scan import ScanRecord
from app.models.environmental import EnvironmentalData
from app.models.image import ScanImage
from app.models.robot import RobotStatus
from datetime import datetime, timedelta
import random

def add_environmental_data(db: Session):
    """为现有扫描添加环境数据"""
    scans = db.query(ScanRecord).all()
    print(f"Adding environmental data for {len(scans)} scans...")
    
    total_created = 0
    for scan in scans:
        # 每个扫描创建5-10个环境数据点
        num_points = random.randint(5, 10)
        
        for j in range(num_points):
            env_data = EnvironmentalData(
                scan_id=scan.id,
                air_temperature=float(scan.avg_air_temp) + random.uniform(-1, 1) if scan.avg_air_temp else random.uniform(25, 30),
                air_humidity=float(scan.avg_humidity) + random.uniform(-5, 5) if scan.avg_humidity else random.uniform(50, 70),
                wind_speed=float(scan.wind_speed) + random.uniform(-1, 1) if scan.wind_speed else random.uniform(3, 6),
                plant_temperature=float(scan.avg_plant_temp) + random.uniform(-1, 1) if scan.avg_plant_temp else random.uniform(26, 32),
                latitude=float(scan.latitude) + (random.random() - 0.5) * 0.001,
                longitude=float(scan.longitude) + (random.random() - 0.5) * 0.001,
                measured_at=scan.completed_at - timedelta(minutes=random.randint(0, 15)) if scan.completed_at else datetime.now()
            )
            db.add(env_data)
            total_created += 1
    
    db.commit()
    print(f"[SUCCESS] Created {total_created} environmental data points")


def add_image_records(db: Session):
    """为现有扫描添加图片记录"""
    scans = db.query(ScanRecord).all()
    print(f"Adding image records for {len(scans)} scans...")
    
    image_types = ['thermal', 'visible', 'panorama']
    total_created = 0
    
    for scan in scans:
        # 每个扫描创建2-4张图片
        num_images = random.randint(2, 4)
        
        for j in range(num_images):
            image_type = random.choice(image_types)
            
            # 生成本地路径
            date_path = scan.completed_at.strftime("%Y/%m/%d") if scan.completed_at else datetime.now().strftime("%Y/%m/%d")
            file_path = f"uploads/{image_type}/{date_path}/{image_type}_{scan.id}_{j+1}.jpg"
            
            image = ScanImage(
                scan_id=scan.id,
                image_type=image_type,
                file_path=file_path,
                file_size=random.randint(500000, 3000000),
                mime_type="image/jpeg",
                width=random.choice([1920, 2048, 3840]),
                height=random.choice([1080, 1536, 2160]),
                latitude=float(scan.latitude),
                longitude=float(scan.longitude),
                captured_at=scan.completed_at - timedelta(minutes=random.randint(0, 10)) if scan.completed_at else datetime.now(),
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


def add_robot_status(db: Session, count: int = 20):
    """添加机器人状态记录"""
    print(f"Adding {count} robot status records...")
    
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
    print("=" * 70)
    print("Adding Missing Sample Data")
    print("=" * 70)
    
    db = SessionLocal()
    
    try:
        add_environmental_data(db)
        add_image_records(db)
        add_robot_status(db, count=20)
        
        # 显示最终统计
        print("\n" + "=" * 70)
        print("Final Data Summary:")
        print("=" * 70)
        print(f"Scan Records: {db.query(ScanRecord).count()}")
        print(f"Environmental Data: {db.query(EnvironmentalData).count()}")
        print(f"Image Records: {db.query(ScanImage).count()}")
        print(f"Robot Status: {db.query(RobotStatus).count()}")
        print("=" * 70)
        print("\n[SUCCESS] All sample data created!")
        print("\nStart the server: python run.py")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
