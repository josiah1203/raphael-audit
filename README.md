# raphael-audit

Activity feed, audit logs, event replay

## API

- Prefix: `/v1/audit`
- Port: `8093`
- Health: `GET /health`

## Events

_Published and consumed events documented in `openapi.yaml` and raphael-contracts._

## Development

```bash
uv sync
uv run uvicorn raphael_audit.app:app --reload --port 8093
```

Part of the [Raphael Platform](https://github.com/hummingbird-labs) by HummingBird Labs.
