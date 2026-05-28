# KinoMania — Deployment Runbook

Production: **https://kinomaniak.bnbg.pl** · Single EC2 + Docker Compose
(nginx + gunicorn + Postgres), GHCR image, GitHub Actions CD.

## Architecture

nginx (TLS, static/media, reverse proxy) → gunicorn `web` (image from GHCR) →
`postgres` `db`. `certbot` issues/renews the Let's Encrypt cert. Only ports 80/443
are exposed. See `docs/superpowers/specs/2026-05-27-aws-deployment-design.md`.

## One-time provisioning

### 1. Launch EC2
- Ubuntu 24.04 LTS, **t3.small** (2 GB). On t3.micro (1 GB) add a 2 GB swapfile:
  ```bash
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```
- Allocate an **Elastic IP** and associate it with the instance.
- **Security group** inbound: `22` (your IP only), `80` (0.0.0.0/0), `443` (0.0.0.0/0).

### 2. Install Docker
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # log out/in afterwards
```

### 3. Get the code + secrets onto the box
```bash
sudo mkdir -p /opt/kinomania && sudo chown $USER /opt/kinomania
git clone https://github.com/bgozlinski/cinema-booking-system.git /opt/kinomania
cd /opt/kinomania
cp .env.prod.example .env.prod
# Edit .env.prod: SECRET_KEY, POSTGRES_PASSWORD (+ matching DATABASE_URL),
# Gmail SMTP App Password, Stripe TEST keys.
nano .env.prod
```

### 4. Log in to GHCR (image is private)
Create a GitHub PAT (classic) with `read:packages`, then:
```bash
echo <PAT> | docker login ghcr.io -u bgozlinski --password-stdin
```

### 5. GitHub Actions secrets (repo → Settings → Secrets → Actions)
| Secret | Value |
|---|---|
| `SSH_HOST` | EC2 Elastic IP |
| `SSH_USER` | `ubuntu` |
| `SSH_PRIVATE_KEY` | Private key whose public half is in `~/.ssh/authorized_keys` on the box |

(GHCR push uses the built-in `GITHUB_TOKEN` — no secret needed.)

### 6. DNS
At the bnbg.pl registrar, add: **A** record, host `kinomaniak`, value `<Elastic IP>`,
TTL 300. Verify: `dig +short kinomaniak.bnbg.pl` → the Elastic IP.

### 7. Issue the first certificate
```bash
cd /opt/kinomania
./deploy/init-letsencrypt.sh        # set staging=1 inside first to dry-run
```

### 8. Bring up the full stack
```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps   # all healthy?
```
Create the admin user + demo data:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
docker compose -f docker-compose.prod.yml exec web python manage.py seed_db
```

### 9. Stripe webhook (TEST dashboard)
Add endpoint `https://kinomaniak.bnbg.pl/webhooks/stripe/`, copy the
signing secret into `.env.prod` (`STRIPE_WEBHOOK_SECRET`), then:
```bash
docker compose -f docker-compose.prod.yml up -d web
```

### 10. Backup cron
```bash
crontab -e
# Daily 03:00 backup:
0 3 * * * cd /opt/kinomania && ./deploy/backup.sh >> /var/log/kinomania-backup.log 2>&1
```

## Continuous deployment
Push to `main` → CI runs `quality` + `test` → `build-and-push` (GHCR) →
`deploy` (SSH: `deploy/deploy.sh` pulls + restarts + curls `/healthz`).
Watch under the repo's **Actions** tab.

## Manual operations
| Task | Command (from `/opt/kinomania`) |
|---|---|
| Logs | `docker compose -f docker-compose.prod.yml logs -f web` |
| Restart | `docker compose -f docker-compose.prod.yml restart web` |
| Migrate | `docker compose -f docker-compose.prod.yml exec web python manage.py migrate` |
| Shell | `docker compose -f docker-compose.prod.yml exec web python manage.py shell` |
| Manual deploy | `./deploy/deploy.sh` |
| Backup now | `./deploy/backup.sh` |
| Restore | `gunzip -c backups/<file>.sql.gz \| docker compose -f docker-compose.prod.yml exec -T db psql -U kinomania kinomania` |

## Troubleshooting
- **502 from nginx** — `web` not up/healthy: check `docker compose ... logs web`.
- **CSRF 403 on POST** — `CSRF_TRUSTED_ORIGINS` / `ALLOWED_HOSTS` wrong in `.env.prod`.
- **Cert errors** — DNS must resolve to the EIP before `init-letsencrypt.sh`; re-run after fixing.
- **Static 404** — confirm `web` ran `collectstatic` (entrypoint logs) and `static_volume` is shared with nginx.
- **GHCR pull denied on deploy** — re-run `docker login ghcr.io` on the box (PAT expired).
