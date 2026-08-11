from __future__ import annotations

import json
from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dashboard_app.py"

CONTRACT_TITLES = {
    "Latency percentiles",
    "Request traffic",
    "Error rate and breakdown",
    "Cost over time",
    "Input and output tokens",
    "Quality proxy",
}

SAMPLE_EVENTS = [
    {
        "ts": "2026-08-11T10:00:00.000000Z",
        "level": "info",
        "service": "api",
        "event": "request_received",
        "correlation_id": "req-aaaaaaaa",
        "feature": "monitoring",
    },
    {
        "ts": "2026-08-11T10:00:01.000000Z",
        "level": "info",
        "service": "api",
        "event": "response_sent",
        "correlation_id": "req-aaaaaaaa",
        "feature": "monitoring",
        "latency_ms": 150,
        "tokens_in": 30,
        "tokens_out": 120,
        "cost_usd": 0.0019,
        "quality_score": 0.8,
    },
    {
        "ts": "2026-08-11T10:01:00.000000Z",
        "level": "info",
        "service": "api",
        "event": "request_received",
        "correlation_id": "req-bbbbbbbb",
        "feature": "monitoring",
    },
    {
        "ts": "2026-08-11T10:01:03.000000Z",
        "level": "error",
        "service": "api",
        "event": "request_failed",
        "correlation_id": "req-bbbbbbbb",
        "feature": "monitoring",
        "error_type": "RuntimeError",
    },
]


def run_app(monkeypatch, log_path: Path) -> "AppTest":
    # App doc LOG_PATH giong app/logging_config.py, nen test dieu huong bang env.
    monkeypatch.setenv("LOG_PATH", str(log_path))
    app = AppTest.from_file(str(APP_PATH), default_timeout=90)
    app.run()
    return app


def test_dashboard_renders_all_six_contract_panels(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    log_path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in SAMPLE_EVENTS) + "\n",
        encoding="utf-8",
    )

    app = run_app(monkeypatch, log_path)

    assert not app.exception, [str(e) for e in app.exception]
    titles = {header.value for header in app.subheader}
    assert CONTRACT_TITLES.issubset(titles), CONTRACT_TITLES - titles


def test_dashboard_warns_instead_of_crashing_without_logs(
    monkeypatch, tmp_path: Path
) -> None:
    app = run_app(monkeypatch, tmp_path / "khong-ton-tai.jsonl")

    assert not app.exception, [str(e) for e in app.exception]
    assert app.warning, "phai canh bao khi chua co logs.jsonl thay vi no ra traceback"


def test_panel_ids_and_thresholds_match_dashboard_contract() -> None:
    import scripts.dashboard_app as dashboard_app

    contract = dashboard_app.load_contract()
    assert set(contract["panels"]) == {
        "latency",
        "traffic",
        "errors",
        "cost",
        "tokens",
        "quality",
    }
    for panel in contract["panels"].values():
        aggregation, operator, value = dashboard_app.threshold_of(panel)
        # Ngưỡng phải trỏ vào một phép tổng hợp mà panel thực sự tính.
        assert aggregation in panel["aggregations"]
        assert operator in {"lte", "gte"}
        assert isinstance(value, (int, float))


@pytest.mark.parametrize(
    ("operator", "actual", "limit", "expected"),
    [
        ("lte", 2682.0, 3000.0, True),
        ("lte", 3200.0, 3000.0, False),
        ("gte", 0.84, 0.75, True),
        ("gte", 0.60, 0.75, False),
    ],
)
def test_threshold_verdict(operator: str, actual: float, limit: float, expected: bool) -> None:
    import scripts.dashboard_app as dashboard_app

    ok, _ = dashboard_app.verdict(operator, actual, limit)
    assert ok is expected
