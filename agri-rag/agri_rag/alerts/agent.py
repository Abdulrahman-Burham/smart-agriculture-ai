"""Alert agent: rules decide, RAG explains, notifier delivers, scheduler repeats."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Protocol

from ..domain.farm import FarmContext
from ..domain.weather import WeatherService
from ..pipeline import RagPipeline
from .models import Alert, Severity
from .rules import CropProfiles, evaluate

log = logging.getLogger(__name__)


class Notifier(Protocol):
    async def notify(self, alert: Alert) -> None: ...


class LogNotifier:
    """Default notifier. Replace with SMS / WhatsApp / push in production."""

    async def notify(self, alert: Alert) -> None:
        log.info("ALERT farm=%s [%s] %s — %s", alert.farm_id, alert.severity.value, alert.title, alert.message)


class FarmRepository(Protocol):
    async def list_farms(self) -> list[FarmContext]: ...


class AlertAgent:
    def __init__(self, pipeline: RagPipeline, profiles: CropProfiles, max_concurrency: int = 3,
                 weather: WeatherService | None = None):
        self.pipeline, self.profiles, self.weather = pipeline, profiles, weather
        self._sem = asyncio.Semaphore(max_concurrency)

    async def _enrich(self, alert: Alert, ctx: FarmContext) -> None:
        question = f"{alert.title}: {alert.message} إيه اللي أعمله بالتحديد؟"
        async with self._sem:
            res = await self.pipeline.ask(question, farm=ctx)
        if res.grounded:
            alert.guidance, alert.sources = res.answer, res.sources

    async def run(self, ctx: FarmContext, enrich: bool = True, today: date | None = None) -> list[Alert]:
        if self.weather:
            ctx = await self.weather.enrich(ctx) or ctx
        alerts = evaluate(ctx, self.profiles, today)
        if enrich:
            targets = [a for a in alerts if a.severity != Severity.info]
            await asyncio.gather(*(self._enrich(a, ctx) for a in targets), return_exceptions=True)
        return alerts


class AlertScheduler:
    """Periodically evaluates every farm and notifies, with per-(farm, rule) cooldown de-duplication."""

    def __init__(self, repo: FarmRepository, agent: AlertAgent, notifier: Notifier,
                 interval_s: int = 6 * 3600, cooldown_s: int = 24 * 3600):
        self.repo, self.agent, self.notifier = repo, agent, notifier
        self.interval_s, self.cooldown_s = interval_s, cooldown_s
        self._last_sent: dict[tuple[str, str], float] = {}
        self._task: asyncio.Task | None = None

    async def run_once(self) -> list[Alert]:
        sent: list[Alert] = []
        for farm in await self.repo.list_farms():
            for alert in await self.agent.run(farm):
                key, now = (alert.farm_id, alert.rule_id), time.time()
                if now - self._last_sent.get(key, 0) < self.cooldown_s:
                    continue
                await self.notifier.notify(alert)
                self._last_sent[key] = now
                sent.append(alert)
        return sent

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:  # keep the scheduler alive no matter what
                log.exception("alert scheduler iteration failed")
            await asyncio.sleep(self.interval_s)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
