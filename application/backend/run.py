"""
Simple server startup script.
Run: python run.py
"""
import uvicorn

HOSTNAME = "0.0.0.0"

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Pyroscope Dashboard Backend Server...")
    print("=" * 60)
    print("\nServer will start on:")
    print(f"  - {HOSTNAME}:8000")
    print(f"  - API Docs: http://{HOSTNAME}:8000/docs")
    print(f"  - Health Check: http://{HOSTNAME}:8000/health")
    print("\nPress CTRL+C to stop the server")
    print("=" * 60)
    print()
    
    uvicorn.run(
        "app.main:app",
        host=HOSTNAME,  # Listen on all interfaces for remote access
        port=8000,
        reload=True,
        reload_dirs=["app"]
    )
