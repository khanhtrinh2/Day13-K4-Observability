from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import incidents, logging_config
from app.main import app
from app.middleware import resolve_correlation_id

CHAT_BODY = {
    "user_id": "student-01",
    "session_id": "session-01",
    "feature": "qa",
    "message": "What is the refund policy?",
}
ENRICHMENT_FIELDS = {"user_id_hash", "session_id", "feature", "model", "env"}


def read_events(log_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_generated_correlation_id_uses_req_prefix_and_8_hex_chars() -> None:
    assert re.fullmatch(r"req-[0-9a-f]{8}", resolve_correlation_id(None))


def test_valid_caller_id_is_propagated_but_unsafe_input_is_replaced() -> None:
    assert resolve_correlation_id("req-deadbeef") == "req-deadbeef"

    # Xuống dòng sẽ tạo được một dòng JSON giả trong log, phải bị loại bỏ.
    replaced = resolve_correlation_id("spoofed\nfake-log-line")
    assert replaced != "spoofed\nfake-log-line"
    assert re.fullmatch(r"req-[0-9a-f]{8}", replaced)


def test_response_carries_correlation_id_in_header_and_body(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    with TestClient(app) as client:
        response = client.post("/chat", json=CHAT_BODY)

    correlation_id = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.json()["correlation_id"] == correlation_id
    assert float(response.headers["x-response-time-ms"]) >= 0


def test_each_request_gets_a_distinct_correlation_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    with TestClient(app) as client:
        first = client.post("/chat", json=CHAT_BODY).headers["x-request-id"]
        second = client.post("/chat", json=CHAT_BODY).headers["x-request-id"]

    assert first != second


def test_api_logs_share_one_correlation_id_and_carry_enrichment(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.post("/chat", json=CHAT_BODY)

    correlation_id = response.headers["x-request-id"]
    api_events = [event for event in read_events(log_path) if event.get("service") == "api"]
    assert {event["event"] for event in api_events} == {"request_received", "response_sent"}

    for event in api_events:
        assert event["correlation_id"] == correlation_id
        assert ENRICHMENT_FIELDS.issubset(event)
        # user_id thô không được rời khỏi tiến trình.
        assert CHAT_BODY["user_id"] not in json.dumps(event, ensure_ascii=False)


def test_failed_request_stays_traceable(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    incidents.enable("tool_fail")
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/chat", json=CHAT_BODY)
    finally:
        incidents.disable("tool_fail")

    assert response.status_code == 500
    correlation_id = response.headers["x-request-id"]
    assert response.json()["correlation_id"] == correlation_id

    failures = [e for e in read_events(log_path) if e.get("event") == "request_failed"]
    assert [event["correlation_id"] for event in failures] == [correlation_id]


def test_rejected_request_is_enriched_and_kept_out_of_error_rate(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"user_id": "student-01", "session_id": "session-01", "message": ""},
        )

    assert response.status_code == 422
    assert response.json()["correlation_id"] == response.headers["x-request-id"]

    events = read_events(log_path)
    # error_rate_pct = request_failed / request_received; một request bị chặn ở
    # tầng validation không có request_received nên không được đếm là lỗi hệ thống.
    assert not [e for e in events if e.get("event") == "request_failed"]

    rejected = next(e for e in events if e["event"] == "request_rejected")
    assert ENRICHMENT_FIELDS.issubset(rejected)
