# OpenClaw Intelligence API

Hosted FastAPI server exposing OpenClaw intelligence skills as paid API endpoints.

## Setup

```bash
cd api
pip install -r requirements.txt
```

## Configuration

Set environment variables:

```bash
# Comma-separated list of valid API keys
export API_KEYS="key1,key2,key3"

# Keys that get the paid tier (1000 req/day vs 100 for free)
export PAID_API_KEYS="key1"

# Server port (default: 8400)
export PORT=8400
```

## Run

```bash
# Direct
python3 server.py

# With uvicorn
uvicorn api.server:app --host 0.0.0.0 --port 8400

# Dev mode (auto-reload)
uvicorn api.server:app --host 0.0.0.0 --port 8400 --reload
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/niche/discover` | Find niche opportunities |
| POST | `/api/v1/domain/search` | Generate domain candidates for keywords |
| POST | `/api/v1/domain/check` | WHOIS check domains |
| POST | `/api/v1/content/generate` | Generate SEO blog post |
| POST | `/api/v1/affiliate/inject` | Inject affiliate links into markdown |
| GET | `/api/v1/intelligence/dashboard` | Latest intelligence summary |
| GET | `/api/v1/intelligence/trends` | Trend forecasts |
| GET | `/api/v1/intelligence/entities` | Top entities from knowledge graph |
| GET | `/health` | Health check |

## Authentication

All endpoints require an `X-API-Key` header:

```bash
curl -X POST http://localhost:8400/api/v1/niche/discover \
  -H "X-API-Key: your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"topic": "clean beauty"}'
```

If no `API_KEYS` env var is set, the server runs in dev mode (no auth required).

## Rate Limits

- Free tier: 100 requests/day
- Paid tier: 1000 requests/day

Usage is tracked per key per day in `api/usage.json`.

## Example Requests

### Discover Niches
```bash
curl -X POST http://localhost:8400/api/v1/niche/discover \
  -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" \
  -d '{"topic": "sustainable fashion", "depth": "deep"}'
```

### Search Domains
```bash
curl -X POST http://localhost:8400/api/v1/domain/search \
  -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["clean beauty", "organic skincare"], "tlds": [".com", ".co"]}'
```

### Check Domains
```bash
curl -X POST http://localhost:8400/api/v1/domain/check \
  -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" \
  -d '{"domains": ["cleanbeauty.com", "organicskin.co"]}'
```

### Generate Content
```bash
curl -X POST http://localhost:8400/api/v1/content/generate \
  -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" \
  -d '{"niche": "clean-beauty", "topic": "PFAS regulation impact"}'
```

### Dashboard
```bash
curl http://localhost:8400/api/v1/intelligence/dashboard \
  -H "X-API-Key: KEY"
```
