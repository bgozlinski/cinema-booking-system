#!/bin/sh
# Pull the latest image and restart the stack. Run from the repo root on EC2
# (the CD pipeline SSHes in and invokes this).
set -e
cd "$(dirname "$0")/.."

compose="docker compose -f docker-compose.prod.yml"

echo "### Pulling latest web image ..."
$compose pull web

echo "### Restarting stack ..."
$compose up -d

echo "### Pruning dangling images ..."
docker image prune -f

echo "### Smoke check (https://kinomaniak.bnbg.pl/healthz) ..."
# Poll for readiness instead of a fixed sleep: the entrypoint runs migrate +
# collectstatic before gunicorn binds, so a single curl after `sleep 5` races the
# boot and false-fails the deploy with a 502 even though the site comes up fine.
for i in $(seq 1 30); do
    if curl -fsS https://kinomaniak.bnbg.pl/healthz >/dev/null 2>&1; then
        echo "### Healthy after ~$((i * 2))s. Deploy complete."
        exit 0
    fi
    sleep 2
done

echo "### Smoke check FAILED: /healthz not healthy after 60s." >&2
curl -fsS https://kinomaniak.bnbg.pl/healthz || true   # surface the final error
exit 1
