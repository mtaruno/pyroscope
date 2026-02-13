# 数据库设置指南

## 当前配置

根据你的 `.env` 文件：
- 数据库名：`pyroscope_db`
- 用户名：`pyroscope_user`
- 密码：`80363340wch`
- 主机：`localhost:3306`

## 步骤 1：在 MySQL 中创建数据库和用户

打开 **MySQL 8.4 Command Line Client**（从开始菜单），输入 root 密码，然后执行：

```sql
-- 创建数据库
CREATE DATABASE pyroscope_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建用户（如果还没创建）
CREATE USER 'pyroscope_user'@'localhost' IDENTIFIED BY '80363340wch';

-- 授权
GRANT ALL PRIVILEGES ON pyroscope_db.* TO 'pyroscope_user'@'localhost';
FLUSH PRIVILEGES;

-- 验证
SHOW DATABASES;
SELECT user, host FROM mysql.user WHERE user='pyroscope_user';

-- 退出
EXIT;
```

## 步骤 2：运行数据库迁移

在 PowerShell 的虚拟环境中（backend 目录）：

```powershell
# 确保在虚拟环境中
# 提示符应该显示 (venv)

# 运行迁移，创建所有表
alembic upgrade head
```

**成功标志：**
```
INFO  [alembic.runtime.migration] Context impl MySQLImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema
```

## 步骤 3：验证表已创建

回到 MySQL Command Line Client：

```sql
-- 使用数据库
USE pyroscope_db;

-- 查看所有表
SHOW TABLES;

-- 应该看到 5 个表：
-- +---------------------------+
-- | Tables_in_pyroscope_db    |
-- +---------------------------+
-- | environmental_data        |
-- | robot_status              |
-- | scan_images               |
-- | scan_records              |
-- | users                     |
-- +---------------------------+

-- 查看表结构（示例）
DESCRIBE users;
DESCRIBE scan_records;
```

## 创建的表结构

### 1. users（用户表）
- id - 主键
- username - 用户名（唯一）
- email - 邮箱（唯一）
- password_hash - 密码哈希
- robot_id - 关联的机器人ID
- created_at - 创建时间
- is_active - 是否激活

### 2. scan_records（扫描记录表）
- id - 主键
- zone_id - 区域ID
- zone_name - 区域名称
- latitude - 纬度
- longitude - 经度
- gps_accuracy - GPS精度
- scan_area - 扫描面积
- duration - 扫描时长
- risk_level - 风险等级（low/medium/high）
- avg_plant_temp - 平均植物温度
- avg_air_temp - 平均空气温度
- avg_humidity - 平均湿度
- wind_speed - 风速
- temp_diff - 温度差
- fuel_load - 燃料负载
- fuel_density - 燃料密度
- biomass - 生物量
- robot_id - 机器人ID
- user_id - 用户ID（外键）
- completed_at - 完成时间
- created_at - 创建时间

### 3. environmental_data（环境数据表）
- id - 主键
- scan_id - 扫描ID（外键，级联删除）
- air_temperature - 空气温度
- air_humidity - 空气湿度
- wind_speed - 风速
- plant_temperature - 植物温度
- latitude - 纬度
- longitude - 经度
- measured_at - 测量时间
- created_at - 创建时间

### 4. scan_images（扫描图片表）
- id - 主键
- scan_id - 扫描ID（外键，级联删除）
- image_type - 图片类型（thermal/visible/panorama/detail）
- file_path - 文件路径
- file_size - 文件大小
- mime_type - MIME类型
- width - 宽度
- height - 高度
- latitude - 纬度
- longitude - 经度
- captured_at - 拍摄时间
- meta_data - 元数据（JSON）
- created_at - 创建时间

### 5. robot_status（机器人状态表）
- id - 主键
- robot_id - 机器人ID
- battery_level - 电池电量
- storage_used - 已使用存储
- storage_total - 总存储
- signal_strength - 信号强度
- operating_state - 运行状态（idle/scanning/charging/error）
- latitude - 纬度
- longitude - 经度
- recorded_at - 记录时间

## 故障排查

### 错误：Access denied for user
```
ERROR 1045 (28000): Access denied for user 'pyroscope_user'@'localhost'
```
**解决：** 检查密码是否正确，或重新创建用户

### 错误：Unknown database
```
ERROR 1049 (42000): Unknown database 'pyroscope_db'
```
**解决：** 先创建数据库（步骤1）

### 错误：Can't connect to MySQL server
```
sqlalchemy.exc.OperationalError: (2003, "Can't connect to MySQL server")
```
**解决：** 
1. 确认 MySQL 服务正在运行
2. 检查 `.env` 中的连接信息是否正确
