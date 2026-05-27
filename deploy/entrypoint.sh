#!/bin/sh
set -e

echo "### [entrypoint] Applying database migrations ..."
python manage.py migrate --noinput

echo "### [entrypoint] Collecting static files ..."
python manage.py collectstatic --noinput

echo "### [entrypoint] Starting gunicorn on :8000 ..."
exec gunicorn settings.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --access-logfile - \
    --error-logfile -
