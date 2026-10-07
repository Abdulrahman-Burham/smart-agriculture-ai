"""Persistent Conversation & Farm Context Memory with disk backup, TTL + LRU eviction."""
from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Any

_DEFAULT_PERSIST_PATH = Path(__file__).resolve().parent.parent / "storage" / "sessions_memory.json"


class InMemorySessionStore:
    def __init__(
        self,
        max_turns: int = 30,
        ttl_s: int = 604800,
        max_sessions: int = 10_000,
        persist_path: Path | None = _DEFAULT_PERSIST_PATH,
    ):
        self.max_turns, self.ttl_s, self.max_sessions = max_turns, ttl_s, max_sessions
        self.persist_path = persist_path
        self._data: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
        self._context: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self.persist_path or not self.persist_path.exists():
            return
        try:
            raw = json.loads(self.persist_path.read_text(encoding="utf-8"))
            now = time.time()
            for sid, item in (raw.get("sessions") or {}).items():
                ts = float(item.get("ts", 0))
                if now - ts <= self.ttl_s:
                    self._data[sid] = (ts, list(item.get("history") or []))
            for sid, ctx in (raw.get("context") or {}).items():
                if sid in self._data:
                    self._context[sid] = dict(ctx)
        except Exception:
            pass

    def _save_to_disk(self) -> None:
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "sessions": {
                    sid: {"ts": ts, "history": hist}
                    for sid, (ts, hist) in list(self._data.items())[-500:]
                },
                "context": {
                    sid: {k: v for k, v in ctx.items() if k != "last_chunks"}
                    for sid, ctx in self._context.items()
                    if sid in self._data
                },
            }
            self.persist_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def history(self, session_id: str) -> list[dict]:
        with self._lock:
            entry = self._data.get(session_id)
            if not entry or time.time() - entry[0] > self.ttl_s:
                self._data.pop(session_id, None)
                self._context.pop(session_id, None)
                return []
            return list(entry[1])

    def append(self, session_id: str, question: str, answer: str) -> None:
        with self._lock:
            history = self._data.get(session_id, (0.0, []))[1]
            history += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
            self._data[session_id] = (time.time(), history[-2 * self.max_turns:])
            self._data.move_to_end(session_id)
            while len(self._data) > self.max_sessions:
                old_sid, _ = self._data.popitem(last=False)
                self._context.pop(old_sid, None)
            self._save_to_disk()

    def update_context(
        self,
        session_id: str,
        crop: str | None = None,
        governorate: str | None = None,
        area_feddan: float | None = None,
        irrigation_method: str | None = None,
        diagnoses: list[dict] | None = None,
        last_chunks: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Remember crop, governorate, area_feddan, irrigation_method, leaf image diagnoses, and retrieved chunks across turns."""
        with self._lock:
            ctx = self._context.setdefault(session_id, {})
            if crop:
                ctx["crop"] = crop
            if governorate:
                ctx["governorate"] = governorate
            if area_feddan:
                ctx["area_feddan"] = area_feddan
            if irrigation_method:
                ctx["irrigation_method"] = irrigation_method
            if diagnoses:
                existing = ctx.get("diagnoses") or []
                for d in diagnoses:
                    if d not in existing:
                        existing.append(d)
                ctx["diagnoses"] = existing[-5:]
            if last_chunks:
                ctx["last_chunks"] = list(last_chunks)
            return dict(ctx)

    def get_context(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._context.get(session_id) or {})

