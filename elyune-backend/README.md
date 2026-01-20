# Elyune Backend

Django REST Framework API backend with PostgreSQL database, fully Dockerized for development and production.

## Tech Stack

- **Python 3.12** - Programming language
- **Django 6.0.1** - Web framework
- **Django REST Framework 3.16.1** - API toolkit
- **PostgreSQL 16** - Database
- **MinIO** - S3-compatible object storage for media files
- **Docker & Docker Compose** - Containerization
- **Gunicorn** - Production WSGI server
- **uv** - Fast Python package manager

## Features

- ✅ RESTful API with Django REST Framework
- ✅ PostgreSQL database with persistent storage
- ✅ MinIO S3-compatible object storage for media files
- ✅ Docker containerization (web + db + minio)
- ✅ Environment-based configuration
- ✅ CORS support for frontend integration
- ✅ Automatic database migrations on startup
- ✅ Authentication and session management
- ✅ Pagination support (10 items per page)

## Project Structure

```
elyune-backend/
├── config/                 # Django project configuration
│   ├── settings.py        # Main settings (environment-based)
│   ├── urls.py            # URL routing
│   ├── wsgi.py            # WSGI configuration
│   └── asgi.py            # ASGI configuration
├── docker-entrypoint.sh   # Container startup script
├── Dockerfile             # Multi-stage Docker build
├── docker-compose.yml     # Service orchestration
├── .dockerignore          # Docker build exclusions
├── .env                   # Environment variables (local)
├── .env.example           # Environment template
├── requirements.txt       # Python dependencies
├── manage.py              # Django management script
└── README.md              # This file
```

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- Docker Compose v2.0+

### 1. Clone and Setup

```bash
# Navigate to the project directory
cd elyune-backend

# Copy environment template
cp .env.example .env

# Generate a new SECRET_KEY (optional but recommended)
uv run python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Update .env with the generated SECRET_KEY
```

### 2. Build and Start Services

```bash
# Build Docker images (first time only)
docker-compose build

# Start all services (database + web + minio)
docker-compose up

# Or run in background
docker-compose up -d
```

The application will be available at:
- **API**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin/
- **MinIO Console**: http://localhost:9001 (login: minioadmin/minioadmin)
- **MinIO API**: http://localhost:9000

### 3. Create Superuser

```bash
# Create an admin user
docker-compose exec web python3 manage.py createsuperuser
```

Follow the prompts to set username, email, and password.

## Development

### Running Management Commands

```bash
# Create new migrations
docker-compose exec web python3 manage.py makemigrations

# Apply migrations
docker-compose exec web python3 manage.py migrate

# Create superuser
docker-compose exec web python3 manage.py createsuperuser

# Django shell
docker-compose exec web python3 manage.py shell

# Collect static files
docker-compose exec web python3 manage.py collectstatic
```

### Viewing Logs

```bash
# View all logs
docker-compose logs -f

# View web service logs only
docker-compose logs -f web

# View database logs only
docker-compose logs -f db

# View MinIO logs only
docker-compose logs -f minio
```

### Database Access

```bash
# Access PostgreSQL shell
docker-compose exec db psql -U elyune_user -d elyune_db

# Or from host (if port 5432 is exposed)
psql -h localhost -p 5432 -U elyune_user -d elyune_db
```

### MinIO Access

MinIO provides S3-compatible object storage for media files.

**Web Console:**
- URL: http://localhost:9001
- Username: `minioadmin` (or value from `MINIO_ROOT_USER`)
- Password: `minioadmin` (or value from `MINIO_ROOT_PASSWORD`)

**From the Console you can:**
- Create buckets (create a `media` bucket for Django media files)
- Upload/download files
- Manage access policies
- View bucket statistics

**API Endpoint:**
- URL: http://localhost:9000
- Used by Django for programmatic file operations

**Initial Setup:**
1. Access MinIO Console at http://localhost:9001
2. Login with credentials from `.env`
3. Create a bucket named `media` (or your `MINIO_BUCKET_NAME` value)
4. The bucket will be used by Django to store uploaded media files

### Hot Reload

The development setup includes hot-reload by default:
- Any code changes will automatically restart the Django development server
- No need to rebuild containers for Python code changes
- Database changes (migrations) still need to be applied manually

### Adding New Dependencies

```bash
# Add package to requirements.txt
echo "new-package==1.0.0" >> requirements.txt

# Rebuild the web container
docker-compose build web

# Restart services
docker-compose up -d
```

## Environment Variables

Configuration is managed through environment variables. See `.env.example` for all options.

### Django Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (generate new for production) | - |
| `DEBUG` | Enable debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1,0.0.0.0` |

### Database Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_DB` | Database name | `elyune_db` |
| `POSTGRES_USER` | Database user | `elyune_user` |
| `POSTGRES_PASSWORD` | Database password | - |
| `POSTGRES_HOST` | Database host | `db` |
| `POSTGRES_PORT` | Database port | `5432` |

### CORS Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000,http://127.0.0.1:3000` |

### MinIO Settings (S3-Compatible Object Storage)

| Variable | Description | Default |
|----------|-------------|---------|
| `MINIO_ROOT_USER` | MinIO root username | `minioadmin` |
| `MINIO_ROOT_PASSWORD` | MinIO root password | `minioadmin` |
| `MINIO_ENDPOINT` | MinIO server endpoint | `minio:9000` |
| `MINIO_ACCESS_KEY` | Access key for Django | `minioadmin` |
| `MINIO_SECRET_KEY` | Secret key for Django | `minioadmin` |
| `MINIO_USE_SSL` | Use SSL for MinIO connection | `False` |
| `MINIO_BUCKET_NAME` | Bucket name for media files | `media` |

## Docker Commands

### Start Services

```bash
# Start in foreground
docker-compose up

# Start in background
docker-compose up -d

# Start specific service
docker-compose up web
```

### Stop Services

```bash
# Stop services
docker-compose down

# Stop and remove volumes (⚠️ deletes database data)
docker-compose down -v
```

### Rebuild Containers

```bash
# Rebuild all services
docker-compose build

# Rebuild specific service
docker-compose build web

# Rebuild and start (no cache)
docker-compose build --no-cache
docker-compose up
```

### Container Management

```bash
# List running containers
docker-compose ps

# Access web container shell
docker-compose exec web bash

# Access database container shell
docker-compose exec db bash

# View container logs
docker-compose logs -f [service-name]
```

## API Configuration

### REST Framework

- **Authentication**: Session-based authentication
- **Permissions**: Authenticated users only (default)
- **Pagination**: Page number pagination, 10 items per page
- **Renderer**: JSON (default)

### CORS

CORS is configured to allow requests from:
- `http://localhost:3000` (Frontend development)
- `http://127.0.0.1:3000`

Credentials are allowed for authentication.

## Database

### PostgreSQL Container

- **Image**: postgres:16-alpine
- **Port**: 5432 (exposed for development)
- **Volume**: `postgres_data` (persistent storage)
- **Health Check**: Automatic with pg_isready

### Migrations

Migrations run automatically on container startup via `docker-entrypoint.sh`.

To create new migrations:
```bash
docker-compose exec web python3 manage.py makemigrations
docker-compose exec web python3 manage.py migrate
```

### Data Persistence

Database data is stored in a Docker volume named `postgres_data`. This persists across container restarts.

To reset the database:
```bash
docker-compose down -v  # ⚠️ This deletes all data
docker-compose up --build
```

## Local Development Without Docker

The project supports local development without Docker:

1. Create virtual environment:
```bash
uv venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
uv pip install -r requirements.txt
```

3. Run migrations:
```bash
python3 manage.py migrate
```

4. Start development server:
```bash
python3 manage.py runserver
```

**Note**: Without Docker, the app uses SQLite instead of PostgreSQL (automatic fallback).

## Production Deployment

### Environment Variables

For production, ensure:
- ✅ Generate strong `SECRET_KEY`
- ✅ Set `DEBUG=False`
- ✅ Update `ALLOWED_HOSTS` with your domain
- ✅ Use strong database password
- ✅ Update `CORS_ALLOWED_ORIGINS` with frontend domain
- ✅ Don't expose PostgreSQL port
- ✅ Use HTTPS/TLS

### Security Checklist

- [ ] Change `SECRET_KEY` from example
- [ ] Set `DEBUG=False`
- [ ] Configure proper `ALLOWED_HOSTS`
- [ ] Use strong database credentials
- [ ] Enable HTTPS
- [ ] Configure proper CORS origins
- [ ] Set up proper logging
- [ ] Configure static file serving (Nginx/CDN)
- [ ] Set up database backups
- [ ] Configure monitoring and alerts

### Production Server

The `docker-entrypoint.sh` script automatically uses Gunicorn when `DEBUG=False`:

```bash
# Gunicorn configuration
- Workers: 3
- Timeout: 60 seconds
- Bind: 0.0.0.0:8000
```

Recommended: Use Nginx as reverse proxy for SSL termination and static file serving.

## Troubleshooting

### Database Connection Issues

```bash
# Check if database container is running
docker-compose ps

# Check database logs
docker-compose logs db

# Manually test database connection
docker-compose exec web python3 manage.py dbshell
```

### Port Already in Use

If port 8000 or 5432 is already in use:
```bash
# Find process using port
lsof -i :8000
lsof -i :5432

# Kill the process or change ports in docker-compose.yml
```

### Permission Denied

```bash
# Make entrypoint script executable
chmod +x docker-entrypoint.sh

# Fix file ownership (if needed)
sudo chown -R $USER:$USER .
```

### Container Won't Start

```bash
# View detailed logs
docker-compose logs web

# Rebuild containers
docker-compose build --no-cache

# Remove all containers and volumes, start fresh
docker-compose down -v
docker-compose up --build
```

### Docker Build Fails

If the Docker build fails during dependency installation:

```bash
# Clear Docker cache and rebuild
docker builder prune
docker-compose build --no-cache

# If uv/pip errors occur, check Dockerfile is using correct commands
# The Dockerfile uses 'uv pip install' for faster dependency installation

# Alternative: Use standard pip if uv has issues
# Edit Dockerfile to replace 'uv pip install' with standard pip commands
```

**Note**: Initial builds may take 10-15 minutes as they download all dependencies.

### Migration Issues

```bash
# Check migration status
docker-compose exec web python3 manage.py showmigrations

# Fake migrations (if needed)
docker-compose exec web python3 manage.py migrate --fake

# Reset migrations (⚠️ development only)
docker-compose exec web python3 manage.py migrate --fake app_name zero
docker-compose exec web python3 manage.py migrate app_name
```

## Testing

```bash
# Run tests
docker-compose exec web python3 manage.py test

# Run specific test
docker-compose exec web python3 manage.py test app_name.tests.TestClassName

# Run with coverage
docker-compose exec web coverage run --source='.' manage.py test
docker-compose exec web coverage report
```

## Contributing

1. Create a new branch for your feature
2. Make changes and test locally
3. Ensure all tests pass
4. Submit pull request

## License

See LICENSE file for details.

## Support

For issues and questions, please open an issue on the repository.

---

**Built with ❤️ using Django REST Framework**
