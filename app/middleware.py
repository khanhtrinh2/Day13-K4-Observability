from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

# Correlation ID gửi từ client là input không tin cậy. Chỉ nhận chuỗi ngắn,
# không khoảng trắng hay xuống dòng, để không ai chèn được dòng JSON giả vào log.
SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def new_correlation_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"


def resolve_correlation_id(incoming: str | None) -> str:
    """Giữ lại ID của caller nếu hợp lệ, ngược lại sinh ID mới."""
    if incoming and SAFE_CORRELATION_ID.match(incoming):
        return incoming
    return new_correlation_id()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Context của request trước phải được xoá, nếu không worker dùng lại
        # context cũ và log sẽ gắn nhầm user/session.
        clear_contextvars()

        correlation_id = resolve_correlation_id(request.headers.get("x-request-id"))

        # Bind trước call_next để mọi log phát sinh phía sau tự mang correlation_id.
        bind_contextvars(correlation_id=correlation_id)
        # Lưu vào scope để response model và exception handler đều đọc được.
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{elapsed_ms:.1f}"

        return response
