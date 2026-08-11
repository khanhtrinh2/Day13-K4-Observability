"""Dashboard 6 panel cho Day 13, dựng từ data/logs.jsonl.

Nguồn dữ liệu và mọi ngưỡng đều đọc từ config/dashboard.yaml, nên contract là
nguồn chuẩn duy nhất; sửa YAML là dashboard đổi theo, không cần sửa file này.

Chạy:
    streamlit run scripts/dashboard_app.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.metrics import error_rate_pct, percentile

# Palette đã chạy qua validator ở cả light lẫn dark (6/6 check PASS).
SERIES_1 = "#2a78d6"  # blue  - slot categorical 1
SERIES_2 = "#eb6834"  # orange - slot categorical 2
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"
MUTED = "#898781"

CONTRACT_PATH = REPO_ROOT / "config" / "dashboard.yaml"


def resolve_log_path() -> Path:
    """Dùng chung biến LOG_PATH với app/logging_config.py để hai bên không lệch nguồn."""
    raw = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))
    return raw if raw.is_absolute() else REPO_ROOT / raw


# ---------------------------------------------------------------- data loading


def load_contract() -> dict:
    payload = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    dash = payload["dashboard"]
    return {"meta": dash, "panels": {p["id"]: p for p in dash["panels"]}}


def load_events() -> pd.DataFrame:
    log_path = resolve_log_path()
    if not log_path.exists():
        return pd.DataFrame()
    rows = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], format="ISO8601", utc=True)
    df["minute"] = df["ts"].dt.floor("min")
    return df.sort_values("ts")


def threshold_of(panel: dict) -> tuple[str, str, float]:
    t = panel["threshold"]
    return t["aggregation"], t["operator"], t["value"]


def verdict(operator: str, actual: float, limit: float) -> tuple[bool, str]:
    ok = actual <= limit if operator == "lte" else actual >= limit
    symbol = "≤" if operator == "lte" else "≥"
    return ok, f"ngưỡng {symbol} {limit:g}"


def threshold_caption(panel: dict, actual: float) -> None:
    agg, operator, limit = threshold_of(panel)
    ok, text = verdict(operator, actual, limit)
    color = STATUS_GOOD if ok else STATUS_CRITICAL
    label = "ĐẠT" if ok else "VI PHẠM"
    st.markdown(
        f"<span style='color:{color};font-weight:600'>● {label}</span> "
        f"<span style='color:{MUTED}'>&nbsp;{agg} {text} {panel['unit']}</span>",
        unsafe_allow_html=True,
    )


def threshold_rule(limit: float) -> alt.Chart:
    """Đường SLO nằm ngang, vẽ nét đứt để không bị nhầm với dữ liệu."""
    return (
        alt.Chart(pd.DataFrame({"y": [limit]}))
        .mark_rule(color=STATUS_CRITICAL, strokeDash=[6, 4], strokeWidth=2)
        .encode(y="y:Q")
    )


def empty_note(panel_title: str) -> None:
    st.caption(f"Chưa có dữ liệu cho {panel_title} trong khoảng thời gian đã chọn.")


# ------------------------------------------------------------------- panels


def panel_latency(panel: dict, sent: pd.DataFrame) -> None:
    st.subheader(panel["title"])
    if sent.empty:
        empty_note(panel["title"])
        return
    values = sent["latency_ms"].astype(int).tolist()
    p50, p95, p99 = (percentile(values, p) for p in (50, 95, 99))

    c1, c2, c3 = st.columns(3)
    c1.metric("P50", f"{p50:,.0f} ms")
    c2.metric("P95", f"{p95:,.0f} ms")
    c3.metric("P99", f"{p99:,.0f} ms")

    _, _, limit = threshold_of(panel)
    line = (
        alt.Chart(sent)
        .mark_line(color=SERIES_1, strokeWidth=2, point=alt.OverlayMarkDef(size=60))
        .encode(
            x=alt.X("ts:T", title="Thời gian"),
            y=alt.Y("latency_ms:Q", title="Latency (ms)"),
            tooltip=[
                alt.Tooltip("ts:T", title="Thời gian"),
                alt.Tooltip("latency_ms:Q", title="Latency (ms)", format=",.0f"),
                alt.Tooltip("correlation_id:N", title="Correlation ID"),
                alt.Tooltip("feature:N", title="Feature"),
            ],
        )
    )
    st.altair_chart((line + threshold_rule(limit)).properties(height=220))
    threshold_caption(panel, p95)


def panel_traffic(panel: dict, received: pd.DataFrame) -> None:
    st.subheader(panel["title"])
    if received.empty:
        empty_note(panel["title"])
        return
    per_min = received.groupby("minute").size().reset_index(name="requests")
    rate = per_min["requests"].mean()

    c1, c2 = st.columns(2)
    c1.metric("Tổng request", f"{len(received):,}")
    c2.metric("Trung bình", f"{rate:,.1f} req/phút")

    bars = (
        alt.Chart(per_min)
        .mark_bar(color=SERIES_1, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=18)
        .encode(
            x=alt.X("minute:T", title="Thời gian"),
            y=alt.Y("requests:Q", title="Request / phút"),
            tooltip=[
                alt.Tooltip("minute:T", title="Phút"),
                alt.Tooltip("requests:Q", title="Số request"),
            ],
        )
    )
    st.altair_chart(bars.properties(height=200))
    threshold_caption(panel, rate)


def panel_errors(panel: dict, received: pd.DataFrame, failed: pd.DataFrame) -> None:
    st.subheader(panel["title"])
    n_received, n_failed = len(received), len(failed)
    # Contract: count(request_failed) / count(request_received) * 100.
    rate = error_rate_pct(max(n_received - n_failed, 0), n_failed)

    c1, c2 = st.columns(2)
    c1.metric("Error rate", f"{rate:.2f} %")
    c2.metric("Số request lỗi", f"{n_failed:,}")

    if n_failed:
        breakdown = failed["error_type"].value_counts().reset_index()
        breakdown.columns = ["error_type", "count"]
        bars = (
            alt.Chart(breakdown)
            .mark_bar(color=STATUS_CRITICAL, cornerRadiusEnd=4, size=22)
            .encode(
                x=alt.X("count:Q", title="Số lần"),
                y=alt.Y("error_type:N", title="Loại lỗi", sort="-x"),
                tooltip=["error_type:N", "count:Q"],
            )
        )
        st.altair_chart(bars.properties(height=max(90, 40 * len(breakdown))))
    else:
        st.caption(
            "Không có request_failed nào. Lưu ý: sự cố latency giữ error rate ở 0% — "
            "chỉ theo dõi panel này sẽ bỏ sót loại sự cố đó."
        )
    threshold_caption(panel, rate)


def panel_cost(panel: dict, sent: pd.DataFrame) -> None:
    st.subheader(panel["title"])
    if sent.empty:
        empty_note(panel["title"])
        return
    per_min = sent.groupby("minute")["cost_usd"].sum().reset_index()
    total = float(sent["cost_usd"].sum())

    c1, c2 = st.columns(2)
    c1.metric("Tổng chi phí", f"${total:,.4f}")
    c2.metric("Trung bình / request", f"${sent['cost_usd'].mean():,.5f}")

    bars = (
        alt.Chart(per_min)
        .mark_bar(color=SERIES_1, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=18)
        .encode(
            x=alt.X("minute:T", title="Thời gian"),
            y=alt.Y("cost_usd:Q", title="Chi phí (USD)"),
            tooltip=[
                alt.Tooltip("minute:T", title="Phút"),
                alt.Tooltip("cost_usd:Q", title="USD", format=",.5f"),
            ],
        )
    )
    st.altair_chart(bars.properties(height=200))
    threshold_caption(panel, total)


def panel_tokens(panel: dict, sent: pd.DataFrame) -> None:
    st.subheader(panel["title"])
    if sent.empty:
        empty_note(panel["title"])
        return
    tokens_in = int(sent["tokens_in"].sum())
    tokens_out = int(sent["tokens_out"].sum())

    c1, c2 = st.columns(2)
    c1.metric("Tokens in", f"{tokens_in:,}")
    c2.metric("Tokens out", f"{tokens_out:,}")

    per_min = (
        sent.groupby("minute")[["tokens_in", "tokens_out"]]
        .sum()
        .reset_index()
        .melt("minute", var_name="loai", value_name="tokens")
    )
    # Hai series nên bắt buộc có legend; màu đã qua validator ở cả hai chế độ.
    bars = (
        alt.Chart(per_min)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("minute:T", title="Thời gian"),
            y=alt.Y("tokens:Q", title="Số token"),
            color=alt.Color(
                "loai:N",
                title="Loại",
                scale=alt.Scale(
                    domain=["tokens_in", "tokens_out"], range=[SERIES_1, SERIES_2]
                ),
            ),
            xOffset="loai:N",
            tooltip=[
                alt.Tooltip("minute:T", title="Phút"),
                alt.Tooltip("loai:N", title="Loại"),
                alt.Tooltip("tokens:Q", title="Token", format=","),
            ],
        )
    )
    st.altair_chart(bars.properties(height=200))
    threshold_caption(panel, max(tokens_in, tokens_out))


def panel_quality(panel: dict, sent: pd.DataFrame) -> None:
    st.subheader(panel["title"])
    if sent.empty:
        empty_note(panel["title"])
        return
    mean_score = float(sent["quality_score"].mean())
    st.metric("Quality trung bình", f"{mean_score:.3f}")

    _, _, limit = threshold_of(panel)
    line = (
        alt.Chart(sent)
        .mark_line(color=SERIES_1, strokeWidth=2, point=alt.OverlayMarkDef(size=60))
        .encode(
            x=alt.X("ts:T", title="Thời gian"),
            y=alt.Y("quality_score:Q", title="Quality (0–1)", scale=alt.Scale(domain=[0, 1])),
            tooltip=[
                alt.Tooltip("ts:T", title="Thời gian"),
                alt.Tooltip("quality_score:Q", title="Quality", format=".2f"),
                alt.Tooltip("correlation_id:N", title="Correlation ID"),
            ],
        )
    )
    st.altair_chart((line + threshold_rule(limit)).properties(height=220))
    threshold_caption(panel, mean_score)


# --------------------------------------------------------------------- layout


def render(contract: dict) -> None:
    meta, panels = contract["meta"], contract["panels"]
    df = load_events()

    if df.empty:
        st.warning(
            "Chưa có `data/logs.jsonl`. Chạy API rồi `python scripts/load_test.py` trước."
        )
        return

    window = st.session_state.get("window_minutes", meta["time_range_minutes"])
    newest = df["ts"].max()
    cutoff = newest - timedelta(minutes=window) if window else None
    view = df if cutoff is None else df[df["ts"] >= cutoff]

    sent = view[view["event"] == "response_sent"]
    received = view[view["event"] == "request_received"]
    failed = view[view["event"] == "request_failed"]

    st.caption(
        f"Khoảng thời gian: {window} phút gần nhất  ·  "
        f"{len(view)} bản ghi  ·  "
        f"cập nhật lúc {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC  ·  "
        f"tự refresh mỗi {meta['refresh_seconds']}s"
    )
    st.divider()

    row1 = st.columns(2)
    with row1[0]:
        panel_latency(panels["latency"], sent)
    with row1[1]:
        panel_traffic(panels["traffic"], received)

    st.divider()
    row2 = st.columns(2)
    with row2[0]:
        panel_errors(panels["errors"], received, failed)
    with row2[1]:
        panel_cost(panels["cost"], sent)

    st.divider()
    row3 = st.columns(2)
    with row3[0]:
        panel_tokens(panels["tokens"], sent)
    with row3[1]:
        panel_quality(panels["quality"], sent)

    st.divider()
    with st.expander("Xem dữ liệu dạng bảng"):
        # Bảng dữ liệu là kênh truy cập thay thế khi màu không đọc được.
        cols = [
            c
            for c in ["ts", "correlation_id", "feature", "latency_ms", "tokens_in",
                      "tokens_out", "cost_usd", "quality_score"]
            if c in sent.columns
        ]
        st.dataframe(sent[cols], width="stretch", hide_index=True)


def main() -> None:
    contract = load_contract()
    meta = contract["meta"]

    st.set_page_config(page_title=meta["title"], layout="wide")
    st.title(meta["title"])

    with st.sidebar:
        st.header("Bộ lọc")
        options = [15, 30, 60, 180, 0]
        st.session_state["window_minutes"] = st.selectbox(
            "Khoảng thời gian (phút)",
            options,
            index=options.index(meta["time_range_minutes"]),
            format_func=lambda m: "Toàn bộ" if m == 0 else f"{m} phút",
        )
        st.caption(f"Contract: `{CONTRACT_PATH.relative_to(REPO_ROOT)}`")
        st.caption(f"Nguồn: `{resolve_log_path()}`")
        if st.button("Làm mới ngay", width="stretch"):
            st.rerun()

    if hasattr(st, "fragment"):
        st.fragment(render, run_every=meta["refresh_seconds"])(contract)
    else:  # Streamlit cũ không có fragment: vẫn vẽ được, chỉ không tự refresh.
        render(contract)


if __name__ == "__main__":
    main()

