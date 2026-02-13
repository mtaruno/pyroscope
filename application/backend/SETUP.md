# Backend Setup Guide

## Prerequisites

1. **Python 3.9+** installed
2. **MySQL 8.0+** installed and running
3. **pip** package manager

## Step 1: Database Setup

### Create MySQL Database

Connect to MySQL and create the database:

```bash
mysql -u root -p
```

```sql
CREATE DATABASE pyroscope_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pyroscope_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON pyroscope_db.* TO 'pyroscope_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## Step 2: Python Environment Setup

### Create and Activate Virtual Environment

**Windows:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 3: Configure Environment Variables

Edit the `.env` file and update the database credentials:

```env
DATABASE_URL=mysql+pymysql://pyroscope_user:your_secure_password@localhost:3306/pyroscope_db
JWT_SECRET_KEY=your-secret-key-change-this-in-production
```

**Important:** 
- Change `your_secure_password` to match the MySQL user password you created
- Change `JWT_SECRET_KEY` to a strong random string (you can generate one using: `openssl rand -hex 32`)

## Step 4: Run Database Migrations

```bash
# Initialize alembic (only needed once, already done in this project)
# alembic init alembic

# Run migrations to create tables
alembic upgrade head
```

This will create all the necessary tables:
- `users` - User authentication
- `scan_records` - Scan data records
- `environmental_data` - Environmental sensor data
- `scan_images` - Uploaded images
- `robot_status` - Robot status logs

## Step 5: Start the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will start at: http://localhost:8000

## Step 6: Verify Installation

### Check API Documentation

Open your browser and visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Test Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

## Step 7: Create Test User

You can create a test user using the API:

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "robot_01",
    "email": "robot01@example.com",
    "password": "test_password",
    "robot_id": "ROBOT-001"
  }'
```

Then login to get an access token:

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "robot_01",
    "password": "test_password"
  }'
```

Save the `access_token` from the response. You'll need it for authenticated requests.

## Troubleshooting

### Database Connection Error

If you see: `Can't connect to MySQL server`

1. Verify MySQL is running: `systemctl status mysql` (Linux) or check Services (Windows)
2. Check database credentials in `.env` file
3. Verify database exists: `SHOW DATABASES;` in MySQL

### Import Errors

If you see module import errors:

1. Make sure virtual environment is activated
2. Reinstall dependencies: `pip install -r requirements.txt`
3. Check Python version: `python --version` (should be 3.9+)

### Alembic Migration Error

If migrations fail:

1. Check database connection in `.env`
2. Verify alembic.ini configuration
3. Try running: `alembic current` to see current migration state

### Port Already in Use

If port 8000 is already in use:

```bash
# Use a different port
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Next Steps

1. Update `.env` with production-ready JWT secret key
2. Configure CORS origins for your frontend
3. Set up logging and monitoring
4. Configure file size limits for image uploads
5. Set up backup strategy for database and uploaded files

## Development Tips

### Run in Development Mode

```bash
uvicorn app.main:app --reload
```

### Run Tests

```bash
pytest tests/
```

### Create New Migration

After modifying models:

```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### Database Reset

To reset the database (⚠️ destroys all data):

```bash
alembic downgrade base
alembic upgrade head
```
