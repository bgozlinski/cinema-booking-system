# Monitoring (Prometheus + Grafana) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Role division (this project):** user pisze kod aplikacji (`pyproject.toml`, `settings/*.py`, `urls.py`); Claude pisze wszystkie testy i pliki infra (compose, nginx, monitoring config, dashboardy); user uruchamia wszystkie komendy `git`/`gh` sam. Komendy weryfikacyjne (`poetry run pytest`, `docker compose config`) proponuje plan; user/Claude je odpala zależnie od środowiska.

**Goal:** Dodać monitoring metryk Django i Postgresa oraz aktywne probowanie HTTPS/`/healthz`, z wizualizacją w Grafanie, dostępny tylko przez SSH tunnel.

**Architecture:** `django-prometheus` wystawia `/metrics` na serwisie `web` (tryb multiprocess dla 3 workerów gunicorna). Cztery nowe serwisy w `docker-compose.prod.yml` pod `profiles: [monitoring]` (Prometheus, Grafana, postgres_exporter, blackbox_exporter) w tej samej sieci Compose. Prometheus scrapuje cele co 15s; Grafana czyta z Prometheusa. UI bindowane do `127.0.0.1`.

**Tech Stack:** Django 6, gunicorn, Poetry, Docker Compose, Prometheus, Grafana, prometheus_client (multiprocess), nginx.

**Spec:** `docs/superpowers/specs/2026-06-01-monitoring-prometheus-grafana-design.md`

---

## File Structure

**Tworzone:**
- `deploy/gunicorn.conf.py` — hook `child_exit` dla multiprocess metrics.
- `tests/test_metrics.py` — testy endpointu `/metrics` + kolejności middleware.
- `deploy/monitoring/prometheus.yml` — scrape config (3 joby).
- `deploy/monitoring/blackbox.yml` — moduł `http_2xx`.
- `deploy/monitoring/grafana/provisioning/datasources/datasource.yml`
- `deploy/monitoring/grafana/provisioning/dashboards/provider.yml`
- `deploy/monitoring/grafana/dashboards/django.json`
- `deploy/monitoring/grafana/dashboards/postgres.json`
- `deploy/monitoring/grafana/dashboards/blackbox.json`

**Modyfikowane:**
- `pyproject.toml` — dep `django-prometheus`.
- `settings/base.py` — app + 2 middleware.
- `settings/urls.py` — include `/metrics`.
- `deploy/entrypoint.sh` — czyszczenie multiproc dir + gunicorn `--config`.
- `deploy/nginx/default.conf` — deny `/metrics`.
- `docker-compose.prod.yml` — 4 serwisy monitoringu + env/tmpfs na `web` + wolumeny.
- `.env.prod.example` — `GRAFANA_ADMIN_PASSWORD`, `DATA_SOURCE_NAME`.
- `docs/deployment.md` — runbook monitoringu.

---

## Task 1: Dodać zależność `django-prometheus`

**Files:**
- Modify: `pyproject.toml` (sekcja `[tool.poetry.dependencies]`)

- [ ] **Step 1: Dodać dependency**

W `pyproject.toml`, w `[tool.poetry.dependencies]`, po linii `gunicorn`, dodać:

```toml
django-prometheus = "^2.3"
```

`django-prometheus` ciągnie `prometheus_client` jako zależność tranzytywną — potrzebny w Task 3 do trybu multiprocess.

- [ ] **Step 2: Zaktualizować lockfile i zainstalować**

Run: `poetry lock && poetry install`
Expected: `prometheus-client` i `django-prometheus` pojawiają się w `poetry.lock`; instalacja bez błędów.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "build(monitoring): add django-prometheus dependency"
```

---

## Task 2: Wpiąć django-prometheus w Django (settings + urls) — TDD

**Files:**
- Test: `tests/test_metrics.py`
- Modify: `settings/base.py:33-58` (INSTALLED_APPS, MIDDLEWARE)
- Modify: `settings/urls.py:9-18` (urlpatterns)

- [ ] **Step 1: Napisać testy (failing)**

Utworzyć `tests/test_metrics.py`:

```python
"""Prometheus metrics endpoint + middleware wiring (django-prometheus)."""

import pytest
from django.conf import settings


@pytest.mark.django_db
def test_metrics_endpoint_returns_prometheus_exposition(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response["Content-Type"]
    body = response.content.decode()
    # Default process/python collectors are always present in the exposition.
    assert "python_info" in body


@pytest.mark.django_db
def test_metrics_endpoint_records_django_http_metrics(client):
    # Hitting a view should register django-prometheus HTTP middleware metrics.
    client.get("/healthz")
    body = client.get("/metrics").content.decode()

    assert "django_http_requests_total_by_method_total" in body


def test_prometheus_middleware_is_first_and_last():
    assert settings.MIDDLEWARE[0].endswith("PrometheusBeforeMiddleware")
    assert settings.MIDDLEWARE[-1].endswith("PrometheusAfterMiddleware")
```

- [ ] **Step 2: Uruchomić testy — mają FAILować**

Run: `poetry run pytest tests/test_metrics.py -v --no-cov`
Expected: FAIL — `/metrics` zwraca 404 (URL nie istnieje), a `MIDDLEWARE[0]` to `SecurityMiddleware`.

- [ ] **Step 3: Dodać app do INSTALLED_APPS**

W `settings/base.py`, w `INSTALLED_APPS`, dodać `"django_prometheus"` jako pierwszy element listy (przed `django.contrib.admin`):

```python
INSTALLED_APPS = [
    "django_prometheus",
    "django.contrib.admin",
    ...
]
```

- [ ] **Step 4: Owinąć MIDDLEWARE collectorami Prometheusa**

W `settings/base.py`, `MIDDLEWARE` ma mieć `PrometheusBeforeMiddleware` jako **pierwszy** i `PrometheusAfterMiddleware` jako **ostatni** element:

```python
MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]
```

- [ ] **Step 5: Wystawić `/metrics` w urls**

W `settings/urls.py`, dodać include django-prometheus **przed** includami aplikacji pod `""` (żeby nie został przesłonięty). Po linii `path("healthz", ...)`:

```python
from apps.cinema.views import healthz

urlpatterns: list[URLPattern | URLResolver] = [
    path("healthz", healthz, name="healthz"),
    path("", include("django_prometheus.urls")),  # exposes /metrics
    path("admin/", admin.site.urls),
    ...
]
```

- [ ] **Step 6: Uruchomić testy — mają PRZEJŚĆ**

Run: `poetry run pytest tests/test_metrics.py -v --no-cov`
Expected: PASS (3 passed).

- [ ] **Step 7: Regresja — `/healthz` + pełny zestaw**

Run: `poetry run pytest tests/test_healthz.py -v --no-cov`
Expected: PASS — middleware Prometheusa nie psuje istniejących ścieżek.

- [ ] **Step 8: Commit**

```bash
git add settings/base.py settings/urls.py tests/test_metrics.py
git commit -m "feat(monitoring): expose /metrics via django-prometheus"
```

---

## Task 3: Tryb multiprocess gunicorna (3 workery)

Bez tego każdy z 3 workerów ma osobne liczniki w pamięci i Prometheus przy scrape trafia losowo na jeden — wartości HTTP są niespójne. `prometheus_client` agreguje metryki z plików w `PROMETHEUS_MULTIPROC_DIR`.

**Files:**
- Create: `deploy/gunicorn.conf.py`
- Modify: `deploy/entrypoint.sh:11-15`

- [ ] **Step 1: Utworzyć config gunicorna z hookiem child_exit**

Utworzyć `deploy/gunicorn.conf.py`:

```python
"""Gunicorn config. The child_exit hook lets prometheus_client clean up a
worker's metric files when it dies, so multiprocess aggregation stays correct.
Active only when PROMETHEUS_MULTIPROC_DIR is set (see entrypoint.sh)."""


def child_exit(server, worker):
    import os

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
```

- [ ] **Step 2: Czyścić multiproc dir przy starcie + użyć configu**

W `deploy/entrypoint.sh`, przed uruchomieniem gunicorna (po collectstatic) dodać czyszczenie katalogu, i podmienić wywołanie gunicorna na wariant z `--config`:

```sh
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
```

(`PROMETHEUS_MULTIPROC_DIR` i tmpfs ustawiamy na serwisie `web` w Task 6.)

- [ ] **Step 3: Walidacja składni shella**

Run: `sh -n deploy/entrypoint.sh`
Expected: brak outputu (składnia OK).

- [ ] **Step 4: Commit**

```bash
git add deploy/gunicorn.conf.py deploy/entrypoint.sh
git commit -m "feat(monitoring): gunicorn multiprocess metrics support"
```

---

## Task 4: Zablokować `/metrics` publicznie w nginx

`location /` proxuje wszystko do Django, więc bez tego `/metrics` byłby publiczny. Prometheus scrapuje `web:8000/metrics` po sieci dockerowej, nie przez nginx.

**Files:**
- Modify: `deploy/nginx/default.conf:44` (blok HTTPS, przed `location /`)

- [ ] **Step 1: Dodać deny dla /metrics**

W `deploy/nginx/default.conf`, w bloku `server { listen 443 ssl; ... }`, bezpośrednio przed `location / {`, dodać:

```nginx
    # Prometheus metrics are scraped internally over the Docker network only.
    location = /metrics {
        deny all;
        return 404;
    }

    location / {
```

- [ ] **Step 2: Walidacja składni nginx (na EC2 lub lokalnie z dockerem)**

Run: `docker run --rm -v "$PWD/deploy/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" nginx:alpine nginx -t`
Expected: nginx zgłosi błąd o brakujących certach/`options-ssl-nginx.conf` (oczekiwane lokalnie) — ale **nie** błąd składni w naszym bloku. Na EC2, gdzie certy istnieją: `syntax is ok / test is successful`.

- [ ] **Step 3: Commit**

```bash
git add deploy/nginx/default.conf
git commit -m "fix(monitoring): block public access to /metrics in nginx"
```

---

## Task 5: Konfiguracja Prometheusa i blackbox_exportera

**Files:**
- Create: `deploy/monitoring/prometheus.yml`
- Create: `deploy/monitoring/blackbox.yml`

- [ ] **Step 1: Utworzyć `deploy/monitoring/prometheus.yml`**

```yaml
global:
  scrape_interval: 15s
  scrape_timeout: 10s

scrape_configs:
  # Django app (django-prometheus middleware exposition).
  - job_name: django
    metrics_path: /metrics
    static_configs:
      - targets: ["web:8000"]

  # PostgreSQL via postgres_exporter.
  - job_name: postgres
    static_configs:
      - targets: ["postgres_exporter:9187"]

  # Active HTTPS / health probing via blackbox_exporter.
  - job_name: blackbox
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://kinomaniak.bnbg.pl
          - https://kinomaniak.bnbg.pl/healthz
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox_exporter:9115
```

- [ ] **Step 2: Utworzyć `deploy/monitoring/blackbox.yml`**

```yaml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      method: GET
      fail_if_not_ssl: true
      preferred_ip_protocol: ip4
      # valid_status_codes empty -> defaults to any 2xx.
```

- [ ] **Step 3: Walidacja YAML**

Run: `poetry run python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('deploy/monitoring/*.yml')]; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add deploy/monitoring/prometheus.yml deploy/monitoring/blackbox.yml
git commit -m "feat(monitoring): prometheus scrape config + blackbox module"
```

---

## Task 6: Serwisy monitoringu w docker-compose.prod.yml + multiproc na `web`

**Files:**
- Modify: `docker-compose.prod.yml` (serwis `web`; nowe serwisy; `volumes`)

- [ ] **Step 1: Dodać env + tmpfs do serwisu `web`**

W `docker-compose.prod.yml`, w serwisie `web`, dodać `environment` i `tmpfs` (obok istniejących `env_file`, `expose`, `volumes`, `depends_on`):

```yaml
  web:
    image: ghcr.io/bgozlinski/cinema-booking-system:latest
    restart: unless-stopped
    env_file: .env.prod
    environment:
      - PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
    expose:
      - "8000"
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    tmpfs:
      - /tmp/prometheus_multiproc
    depends_on:
      db:
        condition: service_healthy
```

- [ ] **Step 2: Dodać 4 serwisy monitoringu (profile `monitoring`)**

W `docker-compose.prod.yml`, po serwisie `certbot` (przed `volumes:`), dodać:

```yaml
  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    profiles: ["monitoring"]
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=15d
    volumes:
      - ./deploy/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "127.0.0.1:9090:9090"
    depends_on:
      - web

  grafana:
    image: grafana/grafana:latest
    restart: unless-stopped
    profiles: ["monitoring"]
    env_file: .env.prod
    environment:
      # GF_SECURITY_ADMIN_PASSWORD comes from .env.prod via env_file. Do NOT use
      # ${VAR} interpolation here — Compose interpolates from the host env / ./.env,
      # not from a service's env_file, so it would resolve to empty.
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./deploy/monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./deploy/monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - grafana_data:/var/lib/grafana
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      - prometheus

  postgres_exporter:
    image: prometheuscommunity/postgres-exporter:latest
    restart: unless-stopped
    profiles: ["monitoring"]
    env_file: .env.prod
    depends_on:
      db:
        condition: service_healthy

  blackbox_exporter:
    image: prom/blackbox-exporter:latest
    restart: unless-stopped
    profiles: ["monitoring"]
    command:
      - --config.file=/etc/blackbox/blackbox.yml
    volumes:
      - ./deploy/monitoring/blackbox.yml:/etc/blackbox/blackbox.yml:ro
```

- [ ] **Step 3: Dodać wolumeny**

W `docker-compose.prod.yml`, w sekcji `volumes:` na końcu pliku, dodać:

```yaml
volumes:
  pg_data:
  static_volume:
  media_volume:
  prometheus_data:
  grafana_data:
```

- [ ] **Step 4: Walidacja składni compose**

Run (potrzebny `.env.prod` z wartościami z Task 8 — na EC2 lub lokalnie z dummy `.env.prod`):
`docker compose -f docker-compose.prod.yml --profile monitoring config >/dev/null && echo ok`
Expected: `ok` (compose interpoluje zmienne i waliduje strukturę).

- [ ] **Step 5: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat(monitoring): add prometheus/grafana/exporters under monitoring profile"
```

---

## Task 7: Provisioning Grafany + dashboardy

Grafana auto-ładuje datasource i dashboardy z `/etc/grafana/provisioning` i `/var/lib/grafana/dashboards`. Dashboardy referują datasource po `uid: prometheus`.

**Files:**
- Create: `deploy/monitoring/grafana/provisioning/datasources/datasource.yml`
- Create: `deploy/monitoring/grafana/provisioning/dashboards/provider.yml`
- Create: `deploy/monitoring/grafana/dashboards/django.json`
- Create: `deploy/monitoring/grafana/dashboards/postgres.json`
- Create: `deploy/monitoring/grafana/dashboards/blackbox.json`

- [ ] **Step 1: Datasource Prometheus**

`deploy/monitoring/grafana/provisioning/datasources/datasource.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    uid: prometheus
    isDefault: true
```

- [ ] **Step 2: Dashboard provider**

`deploy/monitoring/grafana/provisioning/dashboards/provider.yml`:

```yaml
apiVersion: 1
providers:
  - name: KinoMania
    type: file
    disableDeletion: false
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

- [ ] **Step 3: Dashboard Django**

`deploy/monitoring/grafana/dashboards/django.json`:

```json
{
  "uid": "kinomania-django",
  "title": "KinoMania — Django",
  "schemaVersion": 39,
  "version": 1,
  "time": { "from": "now-1h", "to": "now" },
  "panels": [
    {
      "type": "timeseries",
      "title": "Request rate by method",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "targets": [
        {
          "expr": "sum(rate(django_http_requests_total_by_method_total[5m])) by (method)",
          "legendFormat": "{{method}}"
        }
      ]
    },
    {
      "type": "timeseries",
      "title": "Responses by status",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "targets": [
        {
          "expr": "sum(rate(django_http_responses_total_by_status_total[5m])) by (status)",
          "legendFormat": "{{status}}"
        }
      ]
    },
    {
      "type": "timeseries",
      "title": "Request latency p95 (s)",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 8, "w": 24, "x": 0, "y": 8 },
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(django_http_requests_latency_seconds_by_view_method_bucket[5m])) by (le))",
          "legendFormat": "p95"
        }
      ]
    }
  ]
}
```

- [ ] **Step 4: Dashboard Postgres**

`deploy/monitoring/grafana/dashboards/postgres.json`:

```json
{
  "uid": "kinomania-postgres",
  "title": "KinoMania — PostgreSQL",
  "schemaVersion": 39,
  "version": 1,
  "time": { "from": "now-1h", "to": "now" },
  "panels": [
    {
      "type": "stat",
      "title": "Postgres exporter up",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 6, "w": 6, "x": 0, "y": 0 },
      "targets": [{ "expr": "up{job=\"postgres\"}", "legendFormat": "up" }]
    },
    {
      "type": "timeseries",
      "title": "Active connections",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 6, "w": 18, "x": 6, "y": 0 },
      "targets": [
        {
          "expr": "sum(pg_stat_activity_count) by (datname)",
          "legendFormat": "{{datname}}"
        }
      ]
    },
    {
      "type": "timeseries",
      "title": "Database size (bytes)",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 8, "w": 24, "x": 0, "y": 6 },
      "targets": [
        {
          "expr": "pg_database_size_bytes",
          "legendFormat": "{{datname}}"
        }
      ]
    }
  ]
}
```

- [ ] **Step 5: Dashboard Blackbox**

`deploy/monitoring/grafana/dashboards/blackbox.json`:

```json
{
  "uid": "kinomania-blackbox",
  "title": "KinoMania — Uptime / TLS",
  "schemaVersion": 39,
  "version": 1,
  "time": { "from": "now-6h", "to": "now" },
  "panels": [
    {
      "type": "stat",
      "title": "Probe success",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 6, "w": 12, "x": 0, "y": 0 },
      "targets": [
        { "expr": "probe_success", "legendFormat": "{{instance}}" }
      ]
    },
    {
      "type": "timeseries",
      "title": "Probe duration (s)",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 6, "w": 12, "x": 12, "y": 0 },
      "targets": [
        { "expr": "probe_duration_seconds", "legendFormat": "{{instance}}" }
      ]
    },
    {
      "type": "stat",
      "title": "TLS cert expires in (days)",
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "gridPos": { "h": 6, "w": 24, "x": 0, "y": 6 },
      "targets": [
        {
          "expr": "(probe_ssl_earliest_cert_expiry - time()) / 86400",
          "legendFormat": "{{instance}}"
        }
      ]
    }
  ]
}
```

- [ ] **Step 6: Walidacja JSON/YAML**

Run: `poetry run python -c "import json,glob,yaml; [json.load(open(f)) for f in glob.glob('deploy/monitoring/grafana/dashboards/*.json')]; [yaml.safe_load(open(f)) for f in glob.glob('deploy/monitoring/grafana/provisioning/**/*.yml', recursive=True)]; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add deploy/monitoring/grafana
git commit -m "feat(monitoring): grafana provisioning + django/postgres/blackbox dashboards"
```

---

## Task 8: Zmienne środowiskowe (.env.prod.example)

**Files:**
- Modify: `.env.prod.example`

- [ ] **Step 1: Dodać sekcję monitoringu**

Na końcu `.env.prod.example` dodać:

```ini
# ── Monitoring (profile: monitoring) ───────────────────────────────────
# Grafana admin password (UI bound to 127.0.0.1, reachable via SSH tunnel).
# Name MUST be GF_SECURITY_ADMIN_PASSWORD — Grafana reads it directly from env.
GF_SECURITY_ADMIN_PASSWORD=replace-with-a-strong-password
# postgres_exporter DSN — MUST match the db credentials above. sslmode=disable
# because traffic stays on the internal Docker network.
DATA_SOURCE_NAME=postgresql://kinomania:replace-with-a-strong-password@db:5432/kinomania?sslmode=disable
```

- [ ] **Step 2: Commit**

```bash
git add .env.prod.example
git commit -m "docs(monitoring): document GRAFANA_ADMIN_PASSWORD + DATA_SOURCE_NAME env"
```

> **Uwaga (manualne, poza gitem):** na EC2 dopisać `GRAFANA_ADMIN_PASSWORD` i `DATA_SOURCE_NAME` do realnego `.env.prod` (z prawdziwym hasłem DB) przed uruchomieniem profilu monitoring.

---

## Task 9: Runbook w docs/deployment.md

**Files:**
- Modify: `docs/deployment.md`

- [ ] **Step 1: Dodać sekcję „Monitoring"**

Na końcu `docs/deployment.md` dodać sekcję:

````markdown
## Monitoring (Prometheus + Grafana)

Opcjonalny stack pod profilem `monitoring` — Prometheus, Grafana,
postgres_exporter, blackbox_exporter. UI bindowane do `127.0.0.1`, niedostępne
publicznie. **Nie dotyka** żywych serwisów `web`/`db`/`nginx`.

### Pierwsze uruchomienie (na EC2)

1. Dopisać do `.env.prod`: `GF_SECURITY_ADMIN_PASSWORD` i `DATA_SOURCE_NAME`
   (patrz `.env.prod.example`; `DATA_SOURCE_NAME` musi mieć to samo hasło co `DATABASE_URL`).
2. Uruchomić profil:
   ```sh
   docker compose -f docker-compose.prod.yml --profile monitoring up -d
   ```
3. Sprawdzić, że Prometheus widzi cele: tunel + `http://localhost:9090/targets`
   — wszystkie `UP`.

### Dostęp do UI (SSH tunnel z laptopa)

```sh
ssh -L 3000:localhost:3000 -L 9090:localhost:9090 <user>@<ec2-host>
```
- Grafana: http://localhost:3000 (login `admin` / `GF_SECURITY_ADMIN_PASSWORD`).
- Prometheus: http://localhost:9090.

### Uwaga: CD a profil monitoring

`deploy/deploy.sh` woła `docker compose ... up -d` **bez** `--profile monitoring`,
więc CD nie zatrzyma ani nie zrestartuje serwisów monitoringu — działają dalej.
Po zmianie ich konfiguracji uruchom ręcznie `up -d` z profilem (krok wyżej).

### Zasoby

Stack dokłada ~300–500 MB RAM. Jeśli instancja jest mała (`t2.micro`, 1 GB),
obniż retencję Prometheusa (`--storage.tsdb.retention.time`) lub interwał scrape.
````

- [ ] **Step 2: Commit**

```bash
git add docs/deployment.md
git commit -m "docs(monitoring): runbook for enabling monitoring + SSH tunnel access"
```

---

## Walidacja końcowa (na EC2, po deployu)

- [ ] `docker compose -f docker-compose.prod.yml --profile monitoring up -d` startuje wszystkie kontenery.
- [ ] `http://localhost:9090/targets` (przez tunel): joby `django`, `postgres`, `blackbox` = UP.
- [ ] `https://kinomaniak.bnbg.pl/metrics` z zewnątrz zwraca **404** (deny w nginx działa).
- [ ] Grafana (`http://localhost:3000`): 3 dashboardy widoczne, panele pokazują dane.
- [ ] Panel „TLS cert expires in (days)" pokazuje dodatnią liczbę dni.
