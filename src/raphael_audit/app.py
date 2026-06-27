"""Raphael audit service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

from raphael_contracts.db import ensure_migrations
from raphael_contracts.errors import ErrorResponse
from raphael_audit.core.observability.hardening import metrics_body
from raphael_audit.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_migrations()
    try:
        from raphael_contracts.kafka import start_consumer

        from raphael_audit.core.silver_projector import handle_platform_event

        start_consumer(handle_platform_event, group_id="raphael-audit-silver")
    except Exception:
        pass
    yield


app = FastAPI(title="raphael-audit", version="0.1.0", lifespan=lifespan)
app.include_router(router, prefix="/v1/audit")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "raphael-audit"}


@app.get("/metrics")
def prometheus_metrics() -> PlainTextResponse:
    body, content_type = metrics_body()
    return PlainTextResponse(content=body, media_type=content_type)


@app.exception_handler(Exception)
async def unhandled(_request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=ErrorResponse(code="internal_error", message=str(exc)).model_dump())
