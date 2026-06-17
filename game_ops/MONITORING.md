# Monitoring Plan — Game Ops API

## Overview

This document describes the observability strategy for the Game Ops system
across three layers: metrics, logging, and alerting.

---

## 1. Key Metrics to Track

### API Layer (per endpoint)
| Metric                        | Tool             | Alert threshold        |
|-------------------------------|------------------|------------------------|
| Request rate (req/s)          | Prometheus        | Sudden 3× spike        |
| p95 / p99 latency             | Prometheus        | p95 > 500ms            |
| HTTP 4xx / 5xx error rate     | Prometheus        | > 1% of requests       |
| Active DB connections         | pg_stat_activity  | > 80% of pool size     |

### Business Metrics
| Metric                        | How                         |
|-------------------------------|-----------------------------|
| Matches submitted / minute    | Counter on POST /submit-score |
| Flagged player rate           | Ratio from /dashboard       |
| Season active since           | seasons.started_at          |
| Leaderboard query latency     | Histogram on GET /leaderboard |

---

## 2. Logging Strategy

**Structured JSON logs** — every request logged with:
```json
{
  "timestamp": "2026-06-17T10:00:00Z",
  "method": "POST",
  "path": "/submit-score",
  "status": 200,
  "duration_ms": 45,
  "player_id": "P001",
  "flagged": false
}
```

**Log levels:**
- `INFO`  — every request, every flag event
- `WARN`  — validation errors, unexpected inputs
- `ERROR` — DB connection failures, unhandled exceptions

**Aggregation:** Ship logs to **Loki** (Grafana stack) or **CloudWatch Logs**.

---

## 3. Alerting Rules (Prometheus / Grafana)

```yaml
# High error rate
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
  for: 2m
  annotations:
    summary: "Error rate exceeded 1% over 5 minutes"

# Slow leaderboard
- alert: SlowLeaderboard
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{path="/leaderboard"}[5m])) > 0.5
  for: 3m
  annotations:
    summary: "Leaderboard p95 latency > 500ms"

# High flagged rate (possible bot wave)
- alert: SuspiciousFlagSpike
  expr: increase(flagged_players_total[10m]) > 50
  for: 1m
  annotations:
    summary: "More than 50 players flagged in 10 minutes — possible cheat wave"
```

---

## 4. Health Check Endpoint

Add `GET /health` to the API:
```json
{ "status": "ok", "db": "connected", "active_season": "Season 2" }
```
Used by load balancers and uptime monitors (UptimeRobot, Pingdom).

---

## 5. Database Monitoring

- **pg_stat_statements** — identify slow queries
- **pg_stat_activity**   — monitor connection count
- **Index usage stats**  — confirm indexes on `matches.player_id`, `matches.season_id`, `flagged_players.player_id` are being hit
- **Table bloat**        — monitor `matches` table growth; archive old seasons

---

## 6. Recommended Stack (minimal setup)

```
FastAPI → Prometheus metrics middleware
        → Grafana dashboards
        → Alertmanager (Slack / email)
        → Loki for log aggregation
PostgreSQL → pg_exporter → Prometheus
```

For a managed cloud setup: **Datadog** or **AWS CloudWatch** covers all of
the above with minimal configuration.
