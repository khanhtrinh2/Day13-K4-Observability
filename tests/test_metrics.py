from app import metrics
from app.metrics import error_rate_pct, percentile


def test_percentile_basic() -> None:
    assert percentile([100, 200, 300, 400], 50) >= 100


def test_error_rate_pct_without_requests() -> None:
    assert error_rate_pct(0, 0) == 0.0


def test_error_rate_pct_uses_all_completed_requests() -> None:
    assert error_rate_pct(success_count=95, error_count=5) == 5.0


def test_snapshot_exposes_error_rate_and_breakdown(monkeypatch) -> None:
    monkeypatch.setattr(metrics, "TRAFFIC", 8)
    monkeypatch.setattr(
        metrics,
        "ERRORS",
        metrics.Counter({"TimeoutError": 1, "ValueError": 1}),
    )

    result = metrics.snapshot()

    assert result["total_requests"] == 10
    assert result["error_count"] == 2
    assert result["error_rate_pct"] == 20.0
    assert result["error_breakdown"] == {"TimeoutError": 1, "ValueError": 1}
