# Quick Command Reference

A quick reference for all commands used in this project.

## Initial Setup

```bash
# Copy environment template
cp .env.example .env

# Generate new Django SECRET_KEY
uv run python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Build Docker containers (first time)
docker-compose build

# Start services
docker-compose up
```

## Daily Development

```bash
# Start services (in background)
docker-compose up -d

# View logs (all services)
docker-compose logs -f

# View logs (specific service)
docker-compose logs -f web
docker-compose logs -f db

# Stop services
docker-compose down
```

## Django Management Commands

```bash
# Create migrations
docker-compose exec web python3 manage.py makemigrations

# Apply migrations
docker-compose exec web python3 manage.py migrate

# Create superuser
docker-compose exec web python3 manage.py createsuperuser

# Django shell
docker-compose exec web python3 manage.py shell

# Collect static files
docker-compose exec web python3 manage.py collectstatic

# Run Django check
docker-compose exec web python3 manage.py check
```

## Database Operations

```bash
# Access PostgreSQL shell
docker-compose exec db psql -U elyune_user -d elyune_db

# Access Django database shell
docker-compose exec web python3 manage.py dbshell

# Backup database
docker-compose exec db pg_dump -U elyune_user elyune_db > backup.sql

# Restore database
docker-compose exec -T db psql -U elyune_user elyune_db < backup.sql

# Reset database (⚠️ deletes all data)
docker-compose down -v
docker-compose up --build
```

## Container Management

```bash
# List running containers
docker-compose ps

# Access web container bash
docker-compose exec web bash

# Access database container bash
docker-compose exec db bash

# Restart specific service
docker-compose restart web

# Stop specific service
docker-compose stop web

# Remove stopped containers
docker-compose rm
```

## Rebuild & Clean

```bash
# Rebuild containers
docker-compose build

# Rebuild without cache
docker-compose build --no-cache

# Rebuild specific service
docker-compose build web

# Remove all containers and volumes
docker-compose down -v

# Remove all images
docker-compose down --rmi all

# Full clean rebuild
docker-compose down -v --rmi all
docker-compose build --no-cache
docker-compose up
```

## Dependency Management

```bash
# Add new package to requirements.txt
echo "package-name==1.0.0" >> requirements.txt

# Install in local environment (without Docker)
uv pip install package-name

# Rebuild container after adding dependencies
docker-compose build web
docker-compose up -d
```

## Testing

```bash
# Run all tests
docker-compose exec web python3 manage.py test

# Run specific app tests
docker-compose exec web python3 manage.py test app_name

# Run specific test class
docker-compose exec web python3 manage.py test app_name.tests.TestClassName

# Run specific test method
docker-compose exec web python3 manage.py test app_name.tests.TestClassName.test_method

# Run with verbosity
docker-compose exec web python3 manage.py test --verbosity=2

# Run tests with coverage
docker-compose exec web coverage run --source='.' manage.py test
docker-compose exec web coverage report
docker-compose exec web coverage html
```

## Debugging

```bash
# View container logs (last 100 lines)
docker-compose logs --tail=100 web

# Follow logs in real-time
docker-compose logs -f web

# Check container status
docker-compose ps

# Inspect container
docker inspect elyune_web

# Check Django configuration
docker-compose exec web python3 manage.py diffsettings

# Check database connection
docker-compose exec web python3 -c "import django; django.setup(); from django.db import connection; connection.ensure_connection(); print('Database connected!')"

# Python interactive shell in container
docker-compose exec web python3
```

## Production

```bash
# Build for production
DEBUG=False docker-compose build

# Start in production mode
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View production logs
docker-compose logs --tail=100 -f

# Collect static files for production
docker-compose exec web python3 manage.py collectstatic --noinput
```

## Local Development (Without Docker)

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Install dependencies
uv pip install -r requirements.txt

# Run migrations
python3 manage.py migrate

# Create superuser
python3 manage.py createsuperuser

# Run development server
python3 manage.py runserver

# Deactivate virtual environment
deactivate
```

## Useful Docker Commands

```bash
# View all Docker images
docker images

# Remove unused Docker images
docker image prune

# View all Docker volumes
docker volume ls

# Remove unused Docker volumes
docker volume prune

# Remove all stopped containers
docker container prune

# Clean up everything (containers, networks, images, volumes)
docker system prune -a --volumes

# Check Docker disk usage
docker system df
```

## Git Operations (After Setup Complete)

```bash
# Check git status
git status

# Add all files
git add .

# Commit changes
git commit -m "Initial Django DRF setup with Docker and PostgreSQL"

# Push to remote
git push origin main

# Create new feature branch
git checkout -b feature/your-feature-name
```

## Environment Variables

```bash
# View current environment variables in container
docker-compose exec web env

# Check specific environment variable
docker-compose exec web bash -c 'echo $DEBUG'
docker-compose exec web bash -c 'echo $POSTGRES_HOST'

# Load environment from .env file
set -a && source .env && set +a  # Unix/Linux
```

## Performance & Monitoring

```bash
# View container resource usage
docker stats

# View specific container stats
docker stats elyune_web elyune_db

# Check Django performance
docker-compose exec web python3 manage.py check --deploy

# Run Django system check
docker-compose exec web python3 manage.py check
```

## Common Troubleshooting

```bash
# Fix permission issues
chmod +x docker-entrypoint.sh
sudo chown -R $USER:$USER .

# Find process using port
lsof -i :8000
lsof -i :5432

# Kill process using port
kill -9 $(lsof -t -i:8000)

# Restart Docker Desktop
# macOS: Docker Desktop → Restart
# Linux: sudo systemctl restart docker

# Clear Docker cache
docker builder prune
docker system prune -a
```

## Health Checks

```bash
# Check if database is ready
docker-compose exec db pg_isready -U elyune_user

# Test database connection
docker-compose exec db psql -U elyune_user -d elyune_db -c "SELECT version();"

# Check Django admin
curl http://localhost:8000/admin/

# Check API endpoint
curl http://localhost:8000/api/
```

## Shortcuts

```bash
# Quick restart
docker-compose restart web

# Quick rebuild and start
docker-compose up --build -d

# Quick logs
docker-compose logs -f --tail=50 web

# Quick shell access
docker-compose exec web bash

# Quick database access
docker-compose exec db psql -U elyune_user -d elyune_db

# Quick Django shell
docker-compose exec web python3 manage.py shell
```

## Create New Django App

```bash
# Create new Django app
docker-compose exec web python3 manage.py startapp app_name

# Add to INSTALLED_APPS in config/settings.py
# Then create migrations
docker-compose exec web python3 manage.py makemigrations
docker-compose exec web python3 manage.py migrate
```

---

**Tip**: Add these to your shell aliases for faster access:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias dcup='docker-compose up -d'
alias dcdown='docker-compose down'
alias dclogs='docker-compose logs -f'
alias dcweb='docker-compose exec web bash'
alias dcdb='docker-compose exec db psql -U elyune_user -d elyune_db'
alias dcmigrate='docker-compose exec web python3 manage.py migrate'
alias dcshell='docker-compose exec web python3 manage.py shell'
```
