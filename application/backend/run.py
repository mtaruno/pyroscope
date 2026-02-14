"""
简单的服务器启动脚本（避免Windows权限问题）
直接运行: python run.py
"""
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Pyroscope Dashboard Backend Server...")
    print("=" * 60)
    print("\nServer will start on:")
    print("  - http://127.0.0.1:8000")
    print("  - API Docs: http://127.0.0.1:8000/docs")
    print("  - Health Check: http://127.0.0.1:8000/health")
    print("\nPress CTRL+C to stop the server")
    print("=" * 60)
    print()
    
    uvicorn.run(
        "app.main:app",
        host="10.18.70.16",  # Listen on all interfaces for remote access
        port=8000,
        reload=True,
        reload_dirs=["app"]
    )
