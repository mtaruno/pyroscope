"""Test database connection"""
import sys
from sqlalchemy import create_engine, text
from app.config import settings

def test_connection():
    print("=" * 60)
    print("Testing database connection...")
    print("=" * 60)
    print(f"\nDatabase URL: {settings.DATABASE_URL}")
    
    try:
        # Create engine
        engine = create_engine(settings.DATABASE_URL)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            print(f"\n[SUCCESS] Connection established!")
            print(f"MySQL Version: {version}")
            
            # Check if database exists
            result = conn.execute(text("SELECT DATABASE()"))
            db_name = result.fetchone()[0]
            print(f"Current Database: {db_name}")
            
            # Check existing tables
            result = conn.execute(text("SHOW TABLES"))
            tables = result.fetchall()
            
            if tables:
                print(f"\nExisting tables ({len(tables)}):")
                for table in tables:
                    print(f"  - {table[0]}")
            else:
                print("\n[WARNING] No tables found in database")
                print("   Run: alembic upgrade head")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Database configuration is correct!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Connection failed!")
        print(f"Error message: {e}")
        print("\nPossible causes:")
        print("1. MySQL service is not running")
        print("2. Database 'pyroscope_db' does not exist")
        print("3. User 'pyroscope_user' does not exist or wrong password")
        print("4. Wrong connection info in .env file")
        print("\nCheck DATABASE_SETUP.md for setup instructions")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
