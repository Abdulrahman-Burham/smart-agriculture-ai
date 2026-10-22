"""The RAG pipeline: understand -> retrieve -> ground -> generate (streaming) -> cite."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from .config import Settings
from .domain.farm import LOW_CONFIDENCE, FarmContext
from .domain.weather import WeatherService
from .generation.llm import LLMClient
from .generation.prompts import FALLBACK_ANSWER, SYSTEM_PROMPT, build_user_message
from .nlp.arabic import classify_user_query, tokenize
from .retrieval.hybrid import HybridRetriever, RetrievalResult
from .sessions import InMemorySessionStore

_BRACKET = re.compile(r"\[([^\]]+)\]")
_NUMBER = re.compile(r"\d+")


def extract_cited_ids(answer: str, n_sources: int) -> list[int]:
    """Source numbers cited in the answer, tolerant to "[1]", "[1, 2]" and "[2, farm_context]"."""
    ids = {int(n) for group in _BRACKET.findall(answer) for n in _NUMBER.findall(group)}
    return sorted(i for i in ids if 1 <= i <= n_sources)


@dataclass
class ChatResult:
    answer: str
    grounded: bool
    sources: list[dict]
    session_id: str
    timings: dict = field(default_factory=dict)
    cited_ids: list[int] = field(default_factory=list)
    intent: str = "standard_agricultural"


class RagPipeline:
    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLMClient,
        sessions: InMemorySessionStore,
        settings: Settings,
        weather: WeatherService | None = None,
    ):
        self.retriever, self.llm, self.sessions, self.s = (
            retriever,
            llm,
            sessions,
            settings,
        )
        self.weather = weather

    # -- helpers ------------------------------------------------------------------
    def _retrieval_query(
        self, question: str, history: list[dict], farm: FarmContext | None = None
    ) -> str:
        """Build context-enriched text used for hybrid retrieval across multi-turn conversations.

        * Combines follow-up questions with recent user turns so pronouns/implicit references
          ("طيب أرش إيه؟", "بكام الجرعة؟", "هل ينفع أخلطه؟") resolve to the active crop & disease.
        * Enriches with confident vision diagnoses and active crop from FarmContext.
        """
        query, n_tokens = question, len(tokenize(question))
        prev_user_msgs = [
            m["content"]
            for m in history
            if m.get("role") == "user" and m.get("content")
        ]

        # If there is conversation history and the question is a follow-up or < 18 tokens, include last 2 user turns
        if prev_user_msgs and n_tokens < 18:
            recent_context = " ".join(prev_user_msgs[-2:])
            query = f"{recent_context} {question}"

        if farm:
            labels = [d.label for d in farm.diagnoses if d.confidence >= LOW_CONFIDENCE]
            extra = " ".join(x for x in (farm.crop, *labels) if x)
            if extra and extra not in query:
                query = f"{query} {extra}"
        return query

    @staticmethod
    def _source_payload(result: RetrievalResult) -> list[dict]:
        return [
            {
                "id": i,
                "title": c.metadata.get("title"),
                "source": c.metadata.get("source"),
                "section": c.metadata.get("section"),
                "crop": c.metadata.get("crop"),
                "score": round(c.score, 4),
                "similarity": round(c.similarity, 3)
                if c.similarity is not None
                else None,
                "snippet": c.text[:240],
            }
            for i, c in enumerate(result.chunks, start=1)
        ]

    # -- main entry ---------------------------------------------------------------
    async def stream(
        self,
        question: str,
        session_id: str | None = None,
        farm: FarmContext | None = None,
        crop: str | None = None,
    ) -> AsyncIterator[dict]:
        """Yields events: sources -> token* -> done. Everything the UI needs, in order."""
        t0 = time.perf_counter()
        session_id = session_id or uuid.uuid4().hex
        history = self.sessions.history(session_id)
        sess_ctx = self.sessions.get_context(session_id)

        # Hydrate farm context from session memory if missing in follow-up turn
        if farm is None:
            farm = FarmContext(farm_id=f"session-{session_id[:8]}")
        if not farm.crop and (crop or sess_ctx.get("crop")):
            farm.crop = crop or sess_ctx.get("crop")
        if not farm.governorate and sess_ctx.get("governorate"):
            farm.governorate = sess_ctx.get("governorate")
        if not farm.area_feddan and sess_ctx.get("area_feddan"):
            farm.area_feddan = float(sess_ctx["area_feddan"])
        if not farm.irrigation_method and sess_ctx.get("irrigation_method"):
            from .domain.farm import IrrigationMethod

            try:
                farm.irrigation_method = IrrigationMethod(sess_ctx["irrigation_method"])
            except Exception:
                pass
        if not farm.diagnoses and sess_ctx.get("diagnoses"):
            from .domain.farm import VisionDiagnosis

            farm.diagnoses = [
                VisionDiagnosis(**d) if isinstance(d, dict) else d
                for d in sess_ctx["diagnoses"]
            ]

        crop = crop or farm.crop

        # ── HCI Intelligent Query Understanding & Dynamic Conciseness ──
        has_context = bool(history or farm.diagnoses or farm.crop)
        q_analysis = classify_user_query(question, has_context=has_context)

        # Fast path for non-retrieval intents: Gibberish, Chit-chat, Extreme Ambiguity
        if not q_analysis.requires_retrieval and q_analysis.suggested_fast_response:
            fast_answer = q_analysis.suggested_fast_response
            yield {
                "type": "sources",
                "sources": [],
                "session_id": session_id,
                "glossary_matches": [],
            }
            yield {"type": "token", "text": fast_answer}
            self.sessions.append(session_id, question, fast_answer)
            total = time.perf_counter() - t0
            yield {
                "type": "done",
                "grounded": False,
                "cited_ids": [],
                "weather_source": None,
                "intent": q_analysis.intent,
                "timings": {
                    "retrieval_ms": 0,
                    "ttft_ms": round(total * 1000),
                    "total_ms": round(total * 1000),
                    "within_budget": True,
                },
            }
            return

        # Weather lookup runs concurrently with retrieval so it adds (almost) no latency.
        weather_task = (
            asyncio.create_task(self.weather.enrich(farm)) if self.weather else None
        )
        result = await asyncio.to_thread(
            self.retriever.retrieve,
            self._retrieval_query(question, history, farm),
            crop,
        )
        if weather_task:
            farm = await weather_task
        t_retrieval = time.perf_counter() - t0

        gate = self.s.min_similarity
        grounded = bool(result.chunks) and (gate <= 0 or result.top_similarity >= gate)

        # If this is a follow-up turn in an active conversation and new retrieval scored below gate,
        # retain previous session chunks so the agent can still answer follow-up/memory questions!
        if not grounded and (history or farm.diagnoses):
            prev_chunks = sess_ctx.get("last_chunks") or []
            if prev_chunks:
                result.chunks = prev_chunks
            if result.chunks or history:
                grounded = True

        # Persist updated farm context & chunks into session memory
        self.sessions.update_context(
            session_id,
            crop=crop,
            governorate=farm.governorate if farm else None,
            area_feddan=farm.area_feddan if farm else None,
            irrigation_method=farm.irrigation_method.value
            if farm and farm.irrigation_method
            else None,
            diagnoses=[d.model_dump() for d in farm.diagnoses]
            if farm and farm.diagnoses
            else None,
            last_chunks=result.chunks if grounded and result.chunks else None,
        )

        sources = self._source_payload(result)
        yield {
            "type": "sources",
            "sources": sources,
            "session_id": session_id,
            "glossary_matches": result.glossary_matches,
        }

        answer_parts: list[str] = []
        ttft: float | None = None

        if not grounded:
            answer_parts.append(FALLBACK_ANSWER)
            ttft = time.perf_counter() - t0
            yield {"type": "token", "text": FALLBACK_ANSWER}
        else:
            farm_text = farm.render_arabic() if farm else ""
            user_msg = build_user_message(
                question,
                farm_text,
                result.chunks,
                self.s.context_max_chars,
                history=history,
                dynamic_instruction=q_analysis.dynamic_instruction,
            )
            # Pass recent multi-turn dialogue history + current grounded prompt + dynamic token budget
            recent_history = history[-20:]
            async for piece in self.llm.stream(
                SYSTEM_PROMPT,
                [*recent_history, {"role": "user", "content": user_msg}],
                max_tokens=q_analysis.suggested_max_tokens,
            ):
                if ttft is None:
                    ttft = time.perf_counter() - t0
                answer_parts.append(piece)
                yield {"type": "token", "text": piece}

        answer = "".join(answer_parts).strip()
        self.sessions.append(session_id, question, answer)
        total = time.perf_counter() - t0
        cited = extract_cited_ids(answer, len(sources))
        yield {
            "type": "done",
            "grounded": grounded,
            "cited_ids": cited,
            "weather_source": farm.weather.source if farm and farm.weather else None,
            "intent": q_analysis.intent,
            "timings": {
                "retrieval_ms": round(t_retrieval * 1000),
                "ttft_ms": round((ttft or total) * 1000),
                "total_ms": round(total * 1000),
                "within_budget": (ttft or total) <= self.s.latency_budget_s,
            },
        }

    async def ask(
        self,
        question: str,
        session_id: str | None = None,
        farm: FarmContext | None = None,
        crop: str | None = None,
    ) -> ChatResult:
        answer, sources, done, sid = [], [], {}, session_id or ""
        async for ev in self.stream(question, session_id, farm, crop):
            if ev["type"] == "sources":
                sources, sid = ev["sources"], ev["session_id"]
            elif ev["type"] == "token":
                answer.append(ev["text"])
            else:
                done = ev
        return ChatResult(
            "".join(answer).strip(),
            done.get("grounded", False),
            sources,
            sid,
            done.get("timings", {}),
            done.get("cited_ids", []),
            done.get("intent", "standard_agricultural"),
        )
