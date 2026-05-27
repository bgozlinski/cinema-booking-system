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
sleep 5
curl -fsS https://kinomaniak.bnbg.pl/healthz
echo ""
echo "### Deploy complete."
