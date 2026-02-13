# 快速启动指南

## ✅ 当前状态

### 数据库
- **MySQL 8.4.8** 已安装并运行
- **pyroscope_db** 数据库已创建
- **5 个表** 已创建（scan_records, environmental_data, scan_images, robot_status, alembic_version）
- **示例数据** 已导入：
  - 10 条扫描记录
  - 75 条环境数据点
  - 27 条图片记录
  - 20 条机器人状态

### 系统简化
- ❌ **无用户认证** - 所有 API 直接访问
- ❌ **无 zone_name** - 只使用 zone_id
- ✅ **图片只存路径** - file_path 字段

## 🚀 30秒启动

### 步骤 1：启动后端（终端1）

```powershell
cd "E:\launch project\pyroscope_dashboard\backend"
python run.py
```

**看到这个说明成功：**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 步骤 2：启动前端（终端2）

```powershell
cd "E:\launch project\pyroscope_dashboard"
npm run dev
```

**看到这个说明成功：**
```
VITE v... ready in ... ms
Local: http://localhost:5173/
```

### 步骤 3：访问应用

打开浏览器：
- **前端界面：** http://localhost:5173
- **API 文档：** http://localhost:8000/docs
- **健康检查：** http://localhost:8000/health

## 🎯 功能演示

### 1. 查看地图标记

前端会自动加载 10 个示例扫描点：
- **红色标记** = 高风险区域
- **黄色标记** = 中风险区域
- **绿色标记** = 低风险区域

### 2. 点击标记查看详情

点击任意标记会显示：
- GPS 坐标
- 温湿度数据
- 风险等级
- 燃料负载
- 图片列表（27张图片分布在不同扫描中）

### 3. 查看数据日志

页面底部可以：
- 展开数据表格
- 查看所有扫描记录
- 拖拽调整表格高度

### 4. 模拟新扫描

点击"Start Scan"按钮：
- 进度条动画
- 扫描完成后自动上传到后端
- 新数据立即显示在地图上

## 🔌 API 测试

### 获取所有扫描

```bash
curl http://localhost:8000/api/scans
```

### 获取扫描详情

```bash
curl http://localhost:8000/api/scans/1
```

### 创建新扫描

```bash
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -d '{
    "zone_id": "A-99",
    "latitude": 34.2257,
    "longitude": -117.8512,
    "risk_level": "high",
    "avg_air_temp": 29.3,
    "avg_humidity": 66.0
  }'
```

## 📊 数据库查询示例

打开 MySQL Command Line Client：

```sql
USE pyroscope_db;

-- 查看所有扫描
SELECT id, zone_id, latitude, longitude, risk_level, 
       avg_air_temp, avg_humidity, completed_at 
FROM scan_records 
ORDER BY completed_at DESC;

-- 查看图片记录（只存路径）
SELECT id, scan_id, image_type, file_path, captured_at 
FROM scan_images 
ORDER BY id DESC 
LIMIT 10;

-- 查看环境数据
SELECT id, scan_id, air_temperature, air_humidity, 
       wind_speed, measured_at 
FROM environmental_data 
ORDER BY measured_at DESC 
LIMIT 10;

-- 查看机器人最新状态
SELECT robot_id, battery_level, storage_used, 
       operating_state, latitude, longitude, recorded_at 
FROM robot_status 
ORDER BY recorded_at DESC 
LIMIT 5;

-- 统计各风险等级的扫描数量
SELECT risk_level, COUNT(*) as count 
FROM scan_records 
GROUP BY risk_level;
```

## 📂 文件结构

### 后端关键文件
```
backend/
├── app/
│   ├── main.py              # FastAPI 应用（已简化，无认证）
│   ├── models/              # 数据库模型（4个表）
│   ├── schemas/             # API 数据验证
│   ├── routers/             # API 端点（无认证要求）
│   └── services/            # 业务逻辑
├── run.py                   # 启动脚本
├── create_sample_data.py    # 示例数据生成
├── view_sample_data.py      # 查看数据
└── test_db_connection.py    # 测试连接
```

### 前端关键文件
```
src/
├── services/
│   └── api.js              # API 客户端（已简化，无认证）
├── components/
│   ├── MapView.jsx         # 地图组件
│   ├── Sidebar.jsx         # 侧边栏
│   ├── ScanResults.jsx     # 结果页面
│   └── DataLog.jsx         # 数据日志
└── App.jsx                 # 主应用（已对接后端）
```

## 🔧 机器人上传数据

### Python 示例代码

```python
import requests

API_URL = "http://localhost:8000/api"

# 1. 创建扫描记录
scan_data = {
    "zone_id": "A-15",
    "latitude": 34.2357,
    "longitude": -117.8612,
    "gps_accuracy": 2.1,
    "scan_area": "50 m × 50 m",
    "duration": "15 min 20 sec",
    "risk_level": "medium",
    "avg_plant_temp": 30.5,
    "avg_air_temp": 28.2,
    "avg_humidity": 62.0,
    "wind_speed": 4.5,
    "temp_diff": 2.3,
    "fuel_load": "Medium",
    "fuel_density": 0.65,
    "biomass": 1.4,
    "robot_id": "ROBOT-001",
    "completed_at": "2026-02-07T15:30:00"
}

response = requests.post(f"{API_URL}/scans", json=scan_data)
scan_id = response.json()["scan_id"]
print(f"Scan created with ID: {scan_id}")

# 2. 上传环境数据
env_data = {
    "scan_id": scan_id,
    "data": [
        {
            "air_temperature": 28.5,
            "air_humidity": 63.0,
            "wind_speed": 4.2,
            "plant_temperature": 30.8,
            "latitude": 34.2357,
            "longitude": -117.8612,
            "measured_at": "2026-02-07T15:25:00"
        },
        {
            "air_temperature": 28.8,
            "air_humidity": 62.5,
            "wind_speed": 4.6,
            "plant_temperature": 31.2,
            "latitude": 34.2358,
            "longitude": -117.8613,
            "measured_at": "2026-02-07T15:26:00"
        }
    ]
}

response = requests.post(f"{API_URL}/environmental", json=env_data)
print(f"Environmental data uploaded: {response.json()}")

# 3. 上传图片
files = {
    'file': ('thermal_image.jpg', open('path/to/image.jpg', 'rb'), 'image/jpeg')
}
data = {
    'scan_id': scan_id,
    'image_type': 'thermal',
    'latitude': 34.2357,
    'longitude': -117.8612,
    'captured_at': '2026-02-07T15:27:00'
}

response = requests.post(f"{API_URL}/images/upload", files=files, data=data)
print(f"Image uploaded: {response.json()}")

# 4. 更新机器人状态
status_data = {
    "robot_id": "ROBOT-001",
    "battery_level": 75,
    "storage_used": 5.2,
    "storage_total": 8.0,
    "signal_strength": "Good",
    "operating_state": "idle",
    "latitude": 34.2357,
    "longitude": -117.8612
}

response = requests.post(f"{API_URL}/robot/status", json=status_data)
print(f"Robot status updated: {response.json()}")
```

## 📱 测试工具推荐

### 1. Swagger UI（推荐）
http://localhost:8000/docs
- 交互式 API 测试
- 自动生成请求示例
- 实时查看响应

### 2. curl 命令行

```bash
# 获取数据
curl http://localhost:8000/api/scans

# 创建数据
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -d '{"zone_id":"A-20","latitude":34.23,"longitude":-117.85}'
```

### 3. Postman
导入 OpenAPI 规范：http://localhost:8000/openapi.json

## 🐛 常见问题

### Q1: 前端看不到数据

**检查：**
1. 后端是否运行：`curl http://localhost:8000/health`
2. 浏览器控制台是否有错误（F12）
3. 查看 Network 标签的 API 请求

### Q2: 图片显示不出来

**原因：** 图片记录只存了路径，实际文件不存在

**解决：**
- 上传真实图片通过 API
- 或者在 `backend/uploads/` 目录放置对应路径的图片文件

### Q3: CORS 错误

**解决：** 检查 `backend/.env` 中的 CORS_ORIGINS 是否包含前端地址

## ✅ 成功检查清单

- [ ] 后端启动成功（http://localhost:8000/health 返回 healthy）
- [ ] API 文档可访问（http://localhost:8000/docs）
- [ ] 前端启动成功（http://localhost:5173）
- [ ] 地图显示 10 个标记
- [ ] 点击标记显示详情
- [ ] 数据日志显示记录

## 🎉 完成！

系统已完全配置并运行。现在你可以：

1. 📡 通过 API 上传机器人数据
2. 🗺️ 在前端地图查看数据点
3. 📊 查看详细的温湿度信息
4. 📷 上传和查看照片（只存路径）
5. 🤖 监控机器人状态

**查看更多：** `FRONTEND_INTEGRATION.md`
