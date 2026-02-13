# Pyroscope Dashboard Backend

FastAPI backend for the Pyroscope wildfire monitoring dashboard.

## Features

- RESTful API for robot data collection
- JWT authentication
- MySQL database with SQLAlchemy ORM
- Image upload and storage
- Real-time environmental data collection
- Scan record management

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials and JWT secret
```

4. Initialize database:
```bash
alembic upgrade head
```

5. Run the server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic validation schemas
│   ├── routers/         # API endpoints
│   ├── services/        # Business logic
│   └── utils/           # Utility functions
├── alembic/             # Database migrations
├── uploads/             # Uploaded files storage
└── tests/               # Unit tests
```

## API Endpoints

### Authentication
- POST /api/auth/register - Register new user
- POST /api/auth/login - Login and get JWT token

### Scans
- GET /api/scans - List all scans
- GET /api/scans/{id} - Get scan details
- POST /api/scans - Create new scan record

### Environmental Data
- POST /api/environmental - Upload environmental data

### Images
- POST /api/images/upload - Upload image
- GET /api/images/{id} - Get image

### Robot Status
- GET /api/robot/{robot_id}/status - Get robot status
- POST /api/robot/status - Update robot status
