# 启动后端服务器

## ✅ 数据库已就绪

数据库连接测试通过！
- MySQL 8.4.8
- 数据库：pyroscope_db  
- 6 个表已创建成功

## 🚀 启动服务器（3种方法）

### 方法 1：无热重载模式（推荐，避免权限问题）

```powershell
cd backend
.\venv\Scripts\activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**特点：**
- ✅ 无权限问题
- ❌ 修改代码后需手动重启
- 适合生产环境

### 方法 2：使用 Python 直接运行

创建 `run.py` 文件：

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
```

然后运行：
```powershell
python run.py
```

###方法 3：使用 watchfiles（替代 reload）

```powershell
pip install watchfiles
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 📊 验证服务器启动成功

打开浏览器访问：

1. **健康检查**
   ```
   http://localhost:8000/health
   ```
   应该返回：`{"status": "healthy"}`

2. **API 文档（Swagger UI）**
   ```
   http://localhost:8000/docs
   ```
   可以看到所有 API 端点

3. **API 文档（ReDoc）**
   ```
   http://localhost:8000/redoc
   ```
   另一种文档风格

## 🎯 成功标志

启动成功会看到：

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## 🐛 常见问题

### 问题 1：端口被占用
```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)
```

**解决：**
```powershell
# 查看占用端口的进程
netstat -ano | findstr :8000

# 杀死进程（替换PID）
taskkill /PID <PID> /F

# 或使用其他端口
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### 问题 2：权限错误（WinError 5）
```
PermissionError: [WinError 5] Access is denied
```

**解决：** 使用方法1（无热重载）或方法2

### 问题 3：找不到模块
```
ModuleNotFoundError: No module named 'app'
```

**解决：** 确保在 backend 目录并激活了虚拟环境

## 📝 开发工作流

### 每天开始开发

```powershell
# 1. 进入目录
cd "E:\launch project\pyroscope_dashboard\backend"

# 2. 激活虚拟环境
.\venv\Scripts\activate

# 3. 启动服务器
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. 在另一个终端启动前端
cd ..
npm run dev
```

### 停止服务器

按 **Ctrl + C**

## 🌐 下一步：启动前端

后端启动后，在新终端中：

```powershell
cd "E:\launch project\pyroscope_dashboard"
npm install  # 如果还没安装
npm run dev
```

前端地址：http://localhost:5173

## 📚 API端点列表

启动后可用的 API：

**认证：**
- POST `/api/auth/register` - 注册
- POST `/api/auth/login` - 登录

**扫描数据：**
- GET `/api/scans` - 列表
- GET `/api/scans/{id}` - 详情
- POST `/api/scans` - 创建

**环境数据：**
- POST `/api/environmental` - 上传

**图片：**
- POST `/api/images/upload` - 上传
- GET `/api/images/{id}` - 获取

**机器人：**
- GET `/api/robot/{id}/status` - 状态
- POST `/api/robot/status` - 更新

**系统：**
- GET `/` - 根路径
- GET `/health` - 健康检查
