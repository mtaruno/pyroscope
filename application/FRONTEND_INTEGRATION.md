# 前后端对接指南

## 🎉 系统已简化

### 变更说明

**已删除：**
- ❌ users 表 - 不需要用户认证
- ❌ zone_name 字段 - 只保留 zone_id
- ❌ JWT 认证 - 所有 API 都可以直接访问

**保留：**
- ✅ scan_records - 扫描记录（只存 zone_id）
- ✅ environmental_data - 环境数据
- ✅ scan_images - 图片记录（只存路径 file_path）
- ✅ robot_status - 机器人状态

## 📊 示例数据已创建

数据库中现有：
- **10 条扫描记录** - 不同风险等级、不同位置
- **50-100 条环境数据点** - 每个扫描5-10个数据点
- **20-40 条图片记录** - 每个扫描2-4张图片（只存路径）
- **20 条机器人状态** - 模拟历史状态

## 🚀 启动步骤

### 1. 启动后端

```powershell
cd backend
python run.py
```

**成功标志：**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**测试 API：**
访问 http://localhost:8000/docs

### 2. 测试 API（无需认证）

**获取所有扫描：**
```bash
curl http://localhost:8000/api/scans
```

**响应示例：**
```json
{
  "total": 10,
  "scans": [
    {
      "id": 1,
      "zone_id": "A-01",
      "latitude": 34.2357,
      "longitude": -117.8612,
      "risk_level": "high",
      "completed_at": "2026-02-05T14:30:00",
      "avg_air_temp": 29.5,
      "avg_humidity": 65.0
    }
  ]
}
```

**获取扫描详情：**
```bash
curl http://localhost:8000/api/scans/1
```

**响应包含：**
- 扫描基本信息
- 关联的图片列表（file_path）
- 温湿度、风险等级等

### 3. 启动前端

```powershell
cd "E:\launch project\pyroscope_dashboard"
npm run dev
```

**访问：** http://localhost:5173

## 📡 API 端点（无需认证）

### 扫描数据

**GET /api/scans**
- 参数：`limit`, `offset`, `risk_level`
- 返回：扫描列表

**GET /api/scans/{id}**
- 返回：扫描详情 + 图片列表

**POST /api/scans**
- Body:
```json
{
  "zone_id": "A-01",
  "latitude": 34.2257,
  "longitude": -117.8512,
  "risk_level": "high",
  "avg_air_temp": 29.3,
  "avg_humidity": 66.0
}
```

### 环境数据

**POST /api/environmental**
```json
{
  "scan_id": 1,
  "data": [
    {
      "air_temperature": 29.5,
      "air_humidity": 65.0,
      "measured_at": "2026-02-07T14:20:00"
    }
  ]
}
```

### 图片

**POST /api/images/upload**
- FormData: `scan_id`, `image_type`, `file`
- 返回：图片记录（包含 file_path）

**GET /api/images/{id}**
- 返回：图片文件

### 机器人状态

**GET /api/robot/ROBOT-001/status**
- 返回：最新机器人状态

**POST /api/robot/status**
```json
{
  "robot_id": "ROBOT-001",
  "battery_level": 85,
  "operating_state": "scanning"
}
```

## 🎨 前端对接要点

### API 客户端简化

前端 `src/services/api.js` 已经处理了：
1. ✅ 无需 Token - 直接调用 API
2. ✅ 自动轮询 - 每10秒获取新扫描数据
3. ✅ 错误处理 - 网络错误自动重试

### 数据格式

**前端显示的扫描记录：**
```javascript
{
  id: 1,
  lat: 34.2357,
  lng: -117.8612,
  riskLevel: 'high',
  scanData: {
    zoneId: 'A-01',      // 注意：只有 zone_id，没有 zone_name
    avgAirTemp: 29.3,
    avgHumidity: 66.0,
    images: [            // 图片列表
      {
        id: 1,
        image_type: 'thermal',
        url: '/api/images/1'  // 图片URL
      }
    ]
  }
}
```

### 图片显示

图片只存储了路径（`file_path`），前端通过 API 获取：

```javascript
// 获取图片列表
const scan = await apiClient.getScanDetail(scanId);
const images = scan.images;  // [{id: 1, image_type: 'thermal', url: '/api/images/1'}]

// 显示图片
<img src={`http://localhost:8000${image.url}`} />
```

## 🧪 测试前端功能

### 1. 查看地图标记

打开 http://localhost:5173

应该看到：
- 地图上有10个标记（示例扫描点）
- 标记颜色对应风险等级（红/黄/绿）
- 悬停显示预览信息

### 2. 点击标记查看详情

点击任意标记：
- 显示扫描详情页面
- 包含温度、湿度、风险等级
- 显示图片列表（如果有）

### 3. 查看数据日志

页面底部：
- 可展开的数据表格
- 显示所有历史扫描记录
- 可拖拽调整高度

## 📝 创建新扫描（前端模拟）

前端的"开始扫描"按钮会：
1. 模拟扫描进度
2. 扫描完成后，自动调用 API 上传数据
3. 新扫描会出现在地图上

## 🐛 故障排查

### 前端看不到数据

**检查：**
```powershell
# 1. 后端是否运行
curl http://localhost:8000/health

# 2. 是否有数据
curl http://localhost:8000/api/scans

# 3. 查看浏览器控制台
按 F12 查看 Network 标签
```

### API 调用失败

**常见原因：**
1. 后端未启动
2. 端口被占用
3. CORS 错误（已配置，应该不会）

**解决：**
```powershell
# 重启后端
cd backend
python run.py
```

## 📚 下一步开发

### 上传真实图片

```javascript
// 创建扫描
const response = await apiClient.createScan(scanData);
const scanId = response.scan_id;

// 上传图片
const file = document.querySelector('input[type="file"]').files[0];
await apiClient.uploadImage(scanId, file, {
  image_type: 'thermal',
  latitude: 34.2257,
  longitude: -117.8512
});
```

### 上传环境数据

```javascript
const envData = [
  {
    air_temperature: 29.5,
    air_humidity: 65.0,
    wind_speed: 5.0,
    plant_temperature: 32.8,
    measured_at: new Date().toISOString()
  }
];

await apiClient.uploadEnvironmentalData(scanId, envData);
```

## 📊 数据库查看

想查看数据库内容，可以使用 MySQL Command Line Client：

```sql
USE pyroscope_db;

-- 查看所有扫描
SELECT id, zone_id, latitude, longitude, risk_level, completed_at 
FROM scan_records;

-- 查看图片记录
SELECT id, scan_id, image_type, file_path 
FROM scan_images;

-- 查看环境数据
SELECT id, scan_id, air_temperature, air_humidity 
FROM environmental_data 
LIMIT 10;
```

## ✅ 完成状态

- [x] 数据库简化（去掉 users、zone_name）
- [x] API 简化（去掉认证）
- [x] 创建示例数据（10条扫描 + 环境数据 + 图片记录）
- [x] 前端已对接（自动轮询，显示数据）
- [x] 图片只存路径（file_path）

**系统已就绪！启动后端和前端即可使用。** 🚀
