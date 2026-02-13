"""
查看示例数据脚本
运行: python view_sample_data.py
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.scan import ScanRecord
from app.models.environmental import EnvironmentalData
from app.models.image import ScanImage
from app.models.robot import RobotStatus

def view_data():
    print("=" * 70)
    print("Pyroscope Dashboard - Sample Data Viewer")
    print("=" * 70)
    
    db = SessionLocal()
    
    try:
        # 查看扫描记录
        scans = db.query(ScanRecord).order_by(ScanRecord.completed_at.desc()).limit(5).all()
        print(f"\n[Scan Records] Total: {db.query(ScanRecord).count()}")
        print("-" * 70)
        for scan in scans:
            print(f"ID: {scan.id} | Zone: {scan.zone_id} | Risk: {scan.risk_level} | "
                  f"Temp: {scan.avg_air_temp}C | Completed: {scan.completed_at}")
        
        # 查看环境数据
        env_count = db.query(EnvironmentalData).count()
        print(f"\n[Environmental Data] Total: {env_count}")
        print("-" * 70)
        env_data = db.query(EnvironmentalData).limit(3).all()
        for env in env_data:
            print(f"ID: {env.id} | Scan: {env.scan_id} | "
                  f"Air Temp: {env.air_temperature}C | "
                  f"Humidity: {env.air_humidity}% | "
                  f"Time: {env.measured_at}")
        
        # 查看图片记录
        images = db.query(ScanImage).limit(5).all()
        print(f"\n[Image Records] Total: {db.query(ScanImage).count()}")
        print("-" * 70)
        for img in images:
            print(f"ID: {img.id} | Scan: {img.scan_id} | Type: {img.image_type} | "
                  f"Path: {img.file_path}")
        
        # 查看机器人状态
        robot = db.query(RobotStatus).order_by(RobotStatus.recorded_at.desc()).first()
        print(f"\n[Robot Status] Total: {db.query(RobotStatus).count()}")
        print("-" * 70)
        if robot:
            print(f"Latest Status:")
            print(f"  Robot ID: {robot.robot_id}")
            print(f"  Battery: {robot.battery_level}%")
            print(f"  Storage: {robot.storage_used}/{robot.storage_total} GB")
            print(f"  State: {robot.operating_state}")
            print(f"  Signal: {robot.signal_strength}")
            print(f"  Location: ({robot.latitude}, {robot.longitude})")
            print(f"  Time: {robot.recorded_at}")
        
        print("\n" + "=" * 70)
        print("[SUCCESS] Data summary complete!")
        print("\nNext steps:")
        print("1. Start backend: python run.py")
        print("2. Visit API docs: http://localhost:8000/docs")
        print("3. Test API: curl http://localhost:8000/api/scans")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        db.close()

if __name__ == "__main__":
    view_data()
