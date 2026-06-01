#!/bin/sh
set -e

echo "### [entrypoint] Applying database migrations ..."
python manage.py migrate --noinput

echo "### [entrypoint] Collecting static files ..."
python manage.py collectstatic --noinput

# Prometheus multiprocess metrics: start from a clean dir each boot so dead
# workers from a previous container don't leak stale samples.
if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
    rm -rf "${PROMETHEUS_MULTIPROC_DIR:?}"/* 2>/dev/null || true
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

echo "### [entrypoint] Starting gunicorn on :8000 ..."
exec gunicorn settings.wsgi:application \
    --config deploy/gunicorn.conf.py \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --access-logfile - \
    --error-logfile -
