from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from structlog.contextvars import bind_contextvars

from .agent import LabAgent
from .incidents import disable, enable, status
from .logging_config import configure_logging, get_logger
from .metrics import record_error, snapshot
from .middleware import CorrelationIdMiddleware
from .pii import hash_user_id, summarize_text
from .schemas import ChatRequest, ChatResponse
from .tracing import tracing_enabled

configure_logging()
log = get_logger()
app = FastAPI(title="Day 13 Observability Lab")
app.add_middleware(CorrelationIdMiddleware)
agent = LabAgent()


@app.on_event("startup")
async def startup() -> None:
    log.info(
        "app_started",
        service=os.getenv("APP_NAME", "day13-observability-lab"),
        env=os.getenv("APP_ENV", "dev"),
        payload={"tracing_enabled": tracing_enabled()},
    )


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tracing_enabled": tracing_enabled(), "incidents": status()}


@app.get("/metrics")
async def metrics() -> dict:
    return snapshot()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    # Bind trước dòng log đầu tiên để request_received và response_sent dùng
    # chung một bộ context. user_id thô không bao giờ được ghi xuống log.
    bind_contextvars(
        user_id_hash=hash_user_id(body.user_id),
        session_id=body.session_id,
        feature=body.feature,
        model=agent.model,
        env=os.getenv("APP_ENV", "dev"),
    )

    log.info(
        "request_received",
        service="api",
        payload={"message_preview": summarize_text(body.message)},
    )
    try:
        result = agent.run(
            user_id=body.user_id,
            feature=body.feature,
            session_id=body.session_id,
            message=body.message,
        )
        log.info(
            "response_sent",
            service="api",
            latency_ms=result.latency_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
            payload={"answer_preview": summarize_text(result.answer)},
        )
        return ChatResponse(
            answer=result.answer,
            correlation_id=request.state.correlation_id,
            latency_ms=result.latency_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
        )
    except Exception as exc:  # pragma: no cover
        error_type = type(exc).__name__
        record_error(error_type)
        log.error(
            "request_failed",
            service="api",
            error_type=error_type,
            payload={"detail": str(exc), "message_preview": summarize_text(body.message)},
        )
        raise HTTPException(status_code=500, detail=error_type) from exc


def _correlation_id(request: Request) -> str:
    """Đọc correlation ID do middleware gán; scope được chia sẻ nên handler vẫn thấy."""
    return getattr(request.state, "correlation_id", "unknown")


def _error_response(request: Request, status_code: int, detail: str) -> JSONResponse:
    correlation_id = _correlation_id(request)
    response = JSONResponse(
        status_code=status_code,
        content={"detail": detail, "correlation_id": correlation_id},
    )
    # Handler của Exception được gắn vào ServerErrorMiddleware, nằm NGOÀI
    # CorrelationIdMiddleware, nên middleware không kịp gắn header cho response
    # này. Gắn tại đây để mọi response lỗi đều truy vết ngược được về log.
    response.headers["x-request-id"] = correlation_id
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Lỗi đã được ghi log tại chỗ raise, ở đây chỉ trả correlation_id cho client.
    return _error_response(request, exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Request bị chặn trước khi vào /chat nên bind_contextvars chưa chạy;
    # lấy enrichment trực tiếp từ raw body để log vẫn đủ trường. Trường nào
    # client không gửi thì để None (schema cho phép null).
    raw = exc.body if isinstance(exc.body, dict) else {}

    def _text(field: str) -> str | None:
        value = raw.get(field)
        return value if isinstance(value, str) and value else None

    user_id = _text("user_id")

    # Dùng event riêng: không có request_received tương ứng, nên nếu ghi
    # request_failed thì error_rate_pct sẽ có tử số mà không có mẫu số.
    log.warning(
        "request_rejected",
        service="api",
        error_type="RequestValidationError",
        user_id_hash=hash_user_id(user_id) if user_id else None,
        session_id=_text("session_id"),
        feature=_text("feature"),
        model=agent.model,
        env=os.getenv("APP_ENV", "dev"),
        payload={"detail": summarize_text(str(exc.errors()))},
    )
    return _error_response(request, 422, "RequestValidationError")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Lưới an toàn cho lỗi thoát ra ngoài try/except của /chat.
    error_type = type(exc).__name__
    record_error(error_type)
    log.error(
        "request_failed",
        service="api",
        error_type=error_type,
        correlation_id=_correlation_id(request),
        payload={"detail": summarize_text(str(exc))},
    )
    return _error_response(request, 500, error_type)


@app.post("/incidents/{name}/enable")
async def enable_incident(name: str) -> JSONResponse:
    try:
        enable(name)
        log.warning("incident_enabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/incidents/{name}/disable")
async def disable_incident(name: str) -> JSONResponse:
    try:
        disable(name)
        log.warning("incident_disabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
