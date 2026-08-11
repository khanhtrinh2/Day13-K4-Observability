from __future__ import annotations

import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM, FakeResponse
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .prompt_management import resolve_prompt
from .tracing import get_langfuse_client, observe, tracing_enabled


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @observe(
        name="rag.retrieve",
        capture_input=False,
        capture_output=False,
    )
    def _retrieve(self, message: str) -> list[str]:
        """
        Sub-component trace cho RAG.

        Khi RAG bị chậm hoặc lỗi, Langfuse sẽ hiển thị riêng
        observation rag.retrieve bên trong trace chính.
        """
        started = time.perf_counter()

        try:
            docs = retrieve(message)

            latency_ms = int(
                (time.perf_counter() - started) * 1000
            )

            langfuse_client = get_langfuse_client()

            # Chỉ lưu metadata an toàn, không lưu raw message.
            if hasattr(langfuse_client, "update_current_span"):
                langfuse_client.update_current_span(
                    metadata={
                        "component": "rag",
                        "operation": "retrieve",
                        "doc_count": len(docs),
                        "latency_ms": latency_ms,
                        "query_preview": summarize_text(message),
                    }
                )

            return docs

        except Exception:
            # Exception sẽ được @observe ghi nhận trên observation.
            raise

    @observe(
        name="llm.generate",
        capture_input=False,
        capture_output=False,
    )
    def _generate(self, prompt_text: str) -> FakeResponse:
        """
        Sub-component trace cho LLM.

        Không capture raw prompt/output để tránh đưa PII
        hoặc nội dung nhạy cảm lên trace.
        """
        started = time.perf_counter()

        try:
            response = self.llm.generate(prompt_text)

            latency_ms = int(
                (time.perf_counter() - started) * 1000
            )

            langfuse_client = get_langfuse_client()

            if hasattr(langfuse_client, "update_current_span"):
                langfuse_client.update_current_span(
                    metadata={
                        "component": "llm",
                        "operation": "generate",
                        "model": self.model,
                        "latency_ms": latency_ms,
                        "tokens_in": response.usage.input_tokens,
                        "tokens_out": response.usage.output_tokens,
                    }
                )

            return response

        except Exception:
            raise

    @observe(
        as_type="generation",
        capture_input=False,
        capture_output=False,
    )
    def run(
        self,
        user_id: str,
        feature: str,
        session_id: str,
        message: str,
    ) -> AgentResult:
        started = time.perf_counter()

        # -------------------------
        # RAG sub-component
        # -------------------------
        docs = self._retrieve(message)

        langfuse_client = get_langfuse_client()

        # -------------------------
        # Prompt management
        # -------------------------
        prompt = resolve_prompt(
            langfuse_client,
            feature=feature,
            docs=docs,
            message=message,
            enabled=tracing_enabled(),
        )

        # -------------------------
        # LLM sub-component
        # -------------------------
        response = self._generate(prompt.text)

        quality_score = self._heuristic_quality(
            message,
            response.text,
            docs,
        )

        latency_ms = int(
            (time.perf_counter() - started) * 1000
        )

        cost_usd = self._estimate_cost(
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        # -------------------------
        # Trace metadata
        # -------------------------
        langfuse_client.update_current_trace(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=[
                "lab",
                feature,
                self.model,
            ],
            metadata={
                "prompt_name": prompt.name,
                "prompt_label": prompt.label,
                "prompt_version": prompt.version,
                "prompt_source": prompt.source,
            },
        )
        # -------------------------
        # Generation metadata
        # -------------------------
        langfuse_client.update_current_generation(
            model=self.model,
            metadata={
                "doc_count": len(docs),
                "query_preview": summarize_text(message),
                "prompt_name": prompt.name,
                "prompt_label": prompt.label,
                "prompt_version": prompt.version,
                "prompt_source": prompt.source,
                "prompt_fetch_error": prompt.fetch_error,
            },
            usage_details={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
            cost_details={
                "total": cost_usd,
            },
            prompt=prompt.managed_prompt,
        )

        # -------------------------
        # Metrics
        # -------------------------
        metrics.record_request(
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def _estimate_cost(
        self,
        tokens_in: int,
        tokens_out: int,
    ) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15

        return round(
            input_cost + output_cost,
            6,
        )

    def _heuristic_quality(
        self,
        question: str,
        answer: str,
        docs: list[str],
    ) -> float:
        score = 0.5

        if docs:
            score += 0.2

        if len(answer) > 40:
            score += 0.1

        if (
            question.lower().split()[0:1]
            and any(
                token in answer.lower()
                for token in question.lower().split()[:3]
            )
        ):
            score += 0.1

        if "[REDACTED" in answer:
            score -= 0.2

        return round(
            max(0.0, min(1.0, score)),
            2,
        )