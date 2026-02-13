# Pyroscope Dashboard - 完整部署指南

## 项目概述

这是一个基于 FastAPI + React 的野火监控系统，支持机器人数据采集、照片上传、实时状态监控和地图可视化。

### 技术栈

**后端:**
- FastAPI (Python 3.9+)
- MySQL 8.0+
- SQLAlchemy ORM
- JWT 认证
- Alembic 数据库迁移

**前端:**
- React 18
- Vite
- Leaflet 地图
- Lucide React 图标

## 一、后端部署

### 1.1 环境要求

- Python 3.9+
- MySQL 8.0+
- pip 包管理器

### 1.2 数据库设置

连接到 MySQL 并创建数据库：

```bash
mysql -u root -p
```

```sql
CREATE DATABASE pyroscope_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pyroscope_user'@'localhost' IDENTIFIED BY '80363340wch';
GRANT ALL PRIVILEGES ON pyroscope_db.* TO 'pyroscope_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 1.3 安装后端依赖

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 1.4 配置环境变量

编辑 `backend/.env` 文件：

```env
DATABASE_URL=mysql+pymysql://pyroscope_user:your_secure_password@localhost:3306/pyroscope_db
JWT_SECRET_KEY=your-random-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=10485760
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

**重要：** 生成安全的JWT密钥：
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 1.5 初始化数据库

```bash
cd backend
alembic upgrade head
```

### 1.6 启动后端服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 API 文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 二、前端部署

### 2.1 安装前端依赖

```bash
# 在项目根目录
npm install
```

### 2.2 配置API地址

如果后端不在 localhost:8000，修改 `src/services/api.js` 第一行：

```javascript
const API_BASE_URL = 'http://your-backend-url:8000/api';
```

### 2.3 启动前端开发服务器

```bash
npm run dev
```

访问前端：http://localhost:5173

### 2.4 生产环境构建

```bash
npm run build
```

构建产物在 `dist/` 目录，可部署到任何静态文件服务器。

## 三、使用流程

### 3.1 创建用户账户

使用 curl 或 API 文档创建机器人账户：

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "robot_01",
    "email": "robot01@example.com",
    "password": "secure_password",
    "robot_id": "ROBOT-001"
  }'
```

### 3.2 登录获取 Token

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "robot_01",
    "password": "secure_password"
  }'
```

保存返回的 `access_token`，后续请求需要使用。

### 3.3 机器人上传扫描数据

```bash
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "zone_id": "A-01",
    "zone_name": "Area A-01",
    "latitude": 34.2257,
    "longitude": -117.8512,
    "gps_accuracy": 2.3,
    "scan_area": "50 m × 50 m",
    "duration": "15 min 32 sec",
    "risk_level": "high",
    "avg_plant_temp": 33.0,
    "avg_air_temp": 29.3,
    "avg_humidity": 66.0,
    "wind_speed": 5.2,
    "fuel_load": "High",
    "fuel_density": 0.78,
    "biomass": 1.9,
    "robot_id": "ROBOT-001",
    "completed_at": "2026-02-07T14:30:00"
  }'
```

### 3.4 上传环境数据

```bash
curl -X POST "http://localhost:8000/api/environmental" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "scan_id": 1,
    "data": [
      {
        "air_temperature": 29.5,
        "air_humidity": 65.0,
        "wind_speed": 5.0,
        "plant_temperature": 32.8,
        "latitude": 34.2257,
        "longitude": -117.8512,
        "measured_at": "2026-02-07T14:20:00"
      }
    ]
  }'
```

### 3.5 上传照片

```bash
curl -X POST "http://localhost:8000/api/images/upload" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "scan_id=1" \
  -F "image_type=thermal" \
  -F "file=@/path/to/image.jpg" \
  -F "latitude=34.2257" \
  -F "longitude=-117.8512" \
  -F "captured_at=2026-02-07T14:25:00"
```

### 3.6 更新机器人状态

```bash
curl -X POST "http://localhost:8000/api/robot/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "robot_id": "ROBOT-001",
    "battery_level": 85,
    "storage_used": 3.2,
    "storage_total": 8.0,
    "signal_strength": "good",
    "operating_state": "scanning",
    "latitude": 34.2257,
    "longitude": -117.8512
  }'
```

## 四、前端功能说明

### 4.1 无需登录功能

- 查看地图和历史扫描点
- 点击地图标记查看扫描详情
- 查看扫描数据日志表

### 4.2 登录后可用功能

- 创建新扫描记录
- 实时查看机器人状态
- 上传照片和环境数据
- 自动刷新最新数据

### 4.3 数据轮询

前端会自动轮询以下数据：
- 每 10 秒刷新扫描列表
- 每 5 秒刷新机器人状态（需登录）

## 五、API 端点总结

### 认证
- `POST /api/auth/register` - 注册用户
- `POST /api/auth/login` - 登录获取 Token

### 扫描数据
- `GET /api/scans` - 获取扫描列表（支持分页、过滤）
- `GET /api/scans/{id}` - 获取扫描详情
- `POST /api/scans` - 创建扫描记录（需认证）

### 环境数据
- `POST /api/environmental` - 批量上传环境数据（需认证）

### 图片
- `POST /api/images/upload` - 上传图片（需认证）
- `GET /api/images/{id}` - 获取图片

### 机器人状态
- `GET /api/robot/{robot_id}/status` - 获取机器人状态
- `POST /api/robot/status` - 更新机器人状态（需认证）

## 六、开发和调试

### 6.1 后端开发

```bash
cd backend
# 激活虚拟环境
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 启动开发服务器（自动重载）
uvicorn app.main:app --reload

# 查看日志
# 日志会输出到控制台
```

### 6.2 前端开发

```bash
# 启动开发服务器（热重载）
npm run dev

# 检查代码（如果配置了 ESLint）
npm run lint

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

### 6.3 数据库管理

```bash
# 查看当前迁移状态
alembic current

# 创建新迁移
alembic revision --autogenerate -m "Description"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1

# 重置数据库（⚠️ 删除所有数据）
alembic downgrade base
alembic upgrade head
```

## 七、常见问题

### Q1: 数据库连接失败

**检查项：**
1. MySQL 服务是否运行
2. `.env` 中的数据库凭证是否正确
3. 数据库和用户是否已创建
4. 防火墙是否允许连接

### Q2: CORS 错误

**解决方法：**
在 `backend/.env` 中添加前端地址到 CORS_ORIGINS：
```env
CORS_ORIGINS=["http://localhost:5173","http://your-frontend-url"]
```

### Q3: 图片上传失败

**检查项：**
1. `backend/uploads/` 目录是否存在且可写
2. 文件大小是否超过限制（默认 10MB）
3. 文件类型是否为 JPEG 或 PNG
4. JWT Token 是否有效

### Q4: 前端无法加载数据

**检查项：**
1. 后端服务是否运行（http://localhost:8000/health）
2. API 地址是否正确（`src/services/api.js`）
3. 浏览器控制台是否有错误
4. 网络请求是否成功（查看 Network 标签）

### Q5: Token 过期

**解决方法：**
- 重新登录获取新 Token
- 调整 JWT 过期时间（`.env` 中 JWT_EXPIRATION_MINUTES）

## 八、生产环境注意事项

### 8.1 安全性

1. **更改默认密钥：** 生成强随机 JWT_SECRET_KEY
2. **使用 HTTPS：** 生产环境必须使用 HTTPS
3. **限制 CORS：** 只允许可信域名
4. **数据库安全：** 使用强密码，限制网络访问
5. **日志审计：** 记录所有 API 访问

### 8.2 性能优化

1. **数据库索引：** 已为常用查询字段创建索引
2. **分页查询：** API 默认支持 limit/offset 分页
3. **图片压缩：** 考虑添加图片压缩中间件
4. **CDN：** 静态文件和图片使用 CDN
5. **缓存：** 考虑添加 Redis 缓存热点数据

### 8.3 备份策略

1. **数据库备份：** 
```bash
mysqldump -u pyroscope_user -p pyroscope_db > backup_$(date +%Y%m%d).sql
```

2. **图片备份：** 定期备份 `backend/uploads/` 目录

3. **配置备份：** 备份 `.env` 文件（注意安全）

## 九、技术支持

如遇到问题，请检查：

1. 后端日志：查看 uvicorn 输出
2. 前端控制台：查看浏览器 Console
3. API 文档：http://localhost:8000/docs
4. 数据库日志：检查 MySQL 日志

## 十、许可证

本项目用于野火监控研究。

---

**部署完成！** 🎉

现在你可以：
1. 访问前端查看地图和数据
2. 使用机器人账户上传扫描数据
3. 在地图上查看历史扫描点
4. 点击标记查看详细信息
