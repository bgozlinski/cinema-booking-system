# Monitoring — Prometheus + Grafana

**Data:** 2026-06-01
**Status:** zaakceptowany (design)
**Powiązane:** `docs/deployment.md`, `docs/superpowers/specs/2026-05-27-aws-deployment-design.md`

## Cel

Zbieranie metryk aplikacji Django i bazy Postgres oraz aktywny monitoring
liveness/HTTPS żywej produkcji, z wizualizacją w Grafanie. Dostęp do UI
wyłącznie przez SSH tunnel — żaden panel monitoringu nie jest wystawiony
publicznie. Brak Alertmanagera w tej iteracji.

## Zakres

**W zakresie:**
- Metryki aplikacji Django (HTTP: liczba/latencja/kody statusu) via `django-prometheus`.
- Metryki Postgresa via `postgres_exporter`.
- Liveness (`up`) wszystkich celów + aktywne probowanie publicznego HTTPS
  i `/healthz` + ważność certyfikatu SSL via `blackbox_exporter`.
- Wizualizacja w Grafanie (dashboardy: Django, Postgres, Blackbox).

**Poza zakresem (YAGNI):**
- Alertmanager / alerty (e-mail, Slack).
- Metryki hosta/systemu (`node_exporter`).
- Instrumentacja silnika DB po stronie django-prometheus (Postgresa pokrywa exporter).
- Publiczna ekspozycja paneli, nowy DNS/subdomena, rozszerzanie certbota.

## Architektura

Cztery nowe serwisy w `docker-compose.prod.yml` pod `profiles: [monitoring]`,
w tej samej sieci Compose co `web`/`db`. Toggle: `docker compose --profile monitoring up -d`.

| Serwis | Obraz | Bind | Rola |
|---|---|---|---|
| `prometheus` | `prom/prometheus` | `127.0.0.1:9090` | Scrape + storage (retencja 15d, scrape 15s) |
| `grafana` | `grafana/grafana` | `127.0.0.1:3000` | Dashboardy |
| `postgres_exporter` | `prometheuscommunity/postgres-exporter` | wewn. `:9187` | Metryki Postgresa |
| `blackbox_exporter` | `prom/blackbox-exporter` | wewn. `:9115` | Probowanie HTTPS / `/healthz` / cert |

UI Prometheusa i Grafany bindowane do `127.0.0.1` na EC2 → niewidoczne z internetu.
Dostęp: `ssh -L 3000:localhost:3000 -L 9090:localhost:9090 <ec2>`.

### Przepływ danych

```
web:8000/metrics   ─┐
postgres_exporter  ─┼─► prometheus ──► grafana (datasource)
blackbox_exporter  ─┘     (scrape co 15s)
   └─ probe ─► https://kinomaniak.bnbg.pl , /healthz
```

## Zmiany w aplikacji Django

Kod aplikacji pisze user; Claude proponuje diff i pisze testy.

1. **`pyproject.toml`** — dodać zależność `django-prometheus`.
2. **`settings/base.py`**:
   - `"django_prometheus"` w `INSTALLED_APPS`.
   - `django_prometheus.middleware.PrometheusBeforeMiddleware` jako **pierwszy** element `MIDDLEWARE`.
   - `django_prometheus.middleware.PrometheusAfterMiddleware` jako **ostatni** element `MIDDLEWARE`.
3. **`settings/urls.py`** — `path("", include("django_prometheus.urls"))` (wystawia `/metrics`).

## Zmiany infrastruktury

Pisze Claude.

4. **`deploy/nginx/default.conf`** — w bloku HTTPS dodać
   `location = /metrics { deny all; return 404; }`, aby `/metrics` nigdy nie
   był dostępny publicznie. Prometheus scrapuje `web:8000/metrics` po sieci
   dockerowej, nie przez nginx.
5. **`docker-compose.prod.yml`** — 4 serwisy pod `profiles: [monitoring]`
   + wolumeny `prometheus_data`, `grafana_data`.
6. **`deploy/monitoring/`**:
   - `prometheus.yml` — 3 joby: `web` (`web:8000`), `postgres`
     (`postgres_exporter:9187`), `blackbox` (probe targets via
     `blackbox_exporter:9115`).
   - `blackbox.yml` — moduł `http_2xx` z weryfikacją TLS.
   - `grafana/provisioning/datasources/` — datasource Prometheus.
   - `grafana/provisioning/dashboards/` — provider + 3 dashboardy JSON
     (Django, Postgres exporter, Blackbox).
7. **`.env.prod`** — `GRAFANA_ADMIN_PASSWORD` oraz `DATA_SOURCE_NAME` dla
   postgres_exporter (zbudowany z istniejących creds DB z `.env.prod`).

## Testy

Pisze Claude.

- `/metrics` zwraca 200 i content-type Prometheusa (django-prometheus podłączony poprawnie).
- `/healthz` nadal zwraca 200 (regresja — middleware Prometheusa nie psuje istniejących ścieżek).
- `MIDDLEWARE` zawiera `PrometheusBeforeMiddleware` jako pierwszy i
  `PrometheusAfterMiddleware` jako ostatni element.

## Bezpieczeństwo

- `/metrics` zablokowany w nginx (deny + 404).
- Prometheus i Grafana nasłuchują tylko na `127.0.0.1`; dostęp przez SSH tunnel.
- Brak nowego DNS/certu/portów publicznych.
- Hasło admina Grafany z `.env.prod` (nie hardcode).

## Zasoby EC2

Stack dokłada ~300–500 MB RAM. Jeśli instancja to `t2.micro` (1 GB) — będzie
ciasno. Mitygacja: retencja 15d, scrape 15s; w razie problemów obniżyć
retencję / interwał. Typ instancji zweryfikować na etapie planu implementacji.

## Deployment / runbook

Aktualizacja `docs/deployment.md`:
- jak włączyć monitoring (`docker compose --profile monitoring up -d`),
- jak dostać się do UI przez SSH tunnel,
- jawne ostrzeżenie: **nie ruszamy** żywego stacku `web`/`db`/`nginx`.
