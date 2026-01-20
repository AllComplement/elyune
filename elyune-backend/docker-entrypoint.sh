#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
# Wait for PostgreSQL to be ready
MAX_ATTEMPTS=30
ATTEMPT=0
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" > /dev/null 2>&1; do
  ATTEMPT=$((ATTEMPT + 1))
  if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
    echo "Failed to connect to PostgreSQL after $MAX_ATTEMPTS attempts"
    exit 1
  fi
  echo "PostgreSQL is unavailable - sleeping (attempt $ATTEMPT/$MAX_ATTEMPTS)"
  sleep 2
done

echo "PostgreSQL is up - executing migrations"

# Run database migrations
python3 manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python3 manage.py collectstatic --noinput

# Start server based on DEBUG mode
if [ "$DEBUG" = "True" ]; then
  echo "Starting Django development server..."
  exec python3 manage.py runserver 0.0.0.0:8000
else
  echo "Starting Gunicorn server..."
  exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
fi
