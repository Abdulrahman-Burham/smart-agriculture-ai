"""Deterministic, explainable alert rules.

Design choice: *whether* to alert is decided by transparent rules over farm data (auditable,
testable, zero hallucination risk); the RAG assistant is only used afterwards to explain *what
to do*, grounded in the approved guides. Thresholds live in config/crop_profiles.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from ..domain.farm import FarmContext
from .models import SEVERITY_ORDER, Alert, AlertType, Severity


@dataclass
class CropProfiles:
    defaults: dict
    crops: dict

    @classmethod
    def load(cls, path: Path) -> "CropProfiles":
        if not Path(path).exists():
            return cls({}, {})
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(raw.get("defaults", {}), raw.get("crops", {}))

    def profile(self, crop: str | None) -> dict | None:
        return self.crops.get(crop) if crop else None

    def stage(self, crop: str | None, stage: str | None) -> dict | None:
        prof = self.profile(crop)
        return (prof or {}).get("stages", {}).get(stage) if stage else None


def _days(since: date | None, today: date) -> int | None:
    return (today - since).days if since else None


def irrigation_rule(ctx: FarmContext, p: CropProfiles, today: date) -> Alert | None:
    stage = p.stage(ctx.crop, ctx.growth_stage)
    days = _days(ctx.last_irrigation_date, today)
    if not stage or days is None or not ctx.irrigation_method:
        return None
    intervals = stage["irrigation_interval_days"]
    interval = intervals.get(ctx.irrigation_method.value)
    if interval is None:
        return None
    reasons = [f"آخر ري من {days} يوم، والمعدل المرجعي كل {interval} يوم (مرحلة {ctx.growth_stage})"]
    temp = ctx.weather.temp_c if ctx.weather else None
    heat = (p.profile(ctx.crop) or {}).get("heat_stress_temp_c")
    if temp is not None and heat is not None and temp >= heat:
        interval = max(1, interval - 1)
        reasons.append(f"الحرارة {temp}°م أعلى من حد الإجهاد الحراري ({heat}°م) فبنقلل الفترة بين الريات")
    if days < interval:
        return None
    rain_skip = p.defaults.get("rain_skip_mm", 5)
    rain = ctx.weather.forecast_rain_mm_48h if ctx.weather else None
    if rain is not None and rain >= rain_skip:
        return Alert(farm_id=ctx.farm_id, rule_id="irrigation.postpone_rain", type=AlertType.irrigation,
                     severity=Severity.info, title="أجّل الري", message="الري مستحق بس متوقع أمطار خلال 48 ساعة.",
                     reasons=reasons + [f"متوقع أمطار {rain} مم خلال 48 ساعة"],
                     action="أجّل الري وراجع حالة الأرض بعد المطر.")
    overdue = days - interval
    critical = overdue >= interval * p.defaults.get("critical_overdue_ratio", 0.5)
    return Alert(farm_id=ctx.farm_id, rule_id="irrigation.due", type=AlertType.irrigation,
                 severity=Severity.critical if critical else Severity.warning,
                 title="موعد الري فات" if overdue > 0 else "موعد الري النهاردة",
                 message=f"{ctx.crop} في مرحلة {ctx.growth_stage} محتاج ري.",
                 reasons=reasons + ([f"متأخر {overdue} يوم"] if overdue > 0 else []),
                 action="نفّذ الري في أقرب وقت (الصبح بدري أو آخر النهار).")


def fertilization_rule(ctx: FarmContext, p: CropProfiles, today: date) -> Alert | None:
    stage = p.stage(ctx.crop, ctx.growth_stage)
    days = _days(ctx.last_fertilization_date, today)
    if not stage or days is None:
        return None
    interval = stage["fertilization_interval_days"]
    if days < interval:
        return None
    return Alert(farm_id=ctx.farm_id, rule_id="fertilization.due", type=AlertType.fertilization,
                 severity=Severity.warning, title="موعد التسميد",
                 message=f"عدى {days} يوم على آخر تسميد لـ{ctx.crop}.",
                 reasons=[f"المعدل المرجعي كل {interval} يوم في مرحلة {ctx.growth_stage}"],
                 action="جهّز دفعة التسميد حسب تحليل التربة وتوصية المهندس الزراعي.")


def soil_ph_rule(ctx: FarmContext, p: CropProfiles, today: date) -> Alert | None:
    prof = p.profile(ctx.crop)
    if not prof or not ctx.soil or ctx.soil.ph is None:
        return None
    lo, hi, ph = prof["soil"]["ph_min"], prof["soil"]["ph_max"], ctx.soil.ph
    if lo <= ph <= hi:
        return None
    side = "قلوية" if ph > hi else "حمضية"
    return Alert(farm_id=ctx.farm_id, rule_id="soil.ph_out_of_range", type=AlertType.soil,
                 severity=Severity.warning, title=f"درجة حموضة التربة {side}",
                 message=f"pH التربة {ph} خارج المدى المناسب لـ{ctx.crop} ({lo}–{hi}).",
                 reasons=[f"pH={ph}", f"المدى المرجعي {lo}–{hi}"],
                 action="راجع توصيات تصحيح pH قبل التسميد القادم.")


def soil_salinity_rule(ctx: FarmContext, p: CropProfiles, today: date) -> Alert | None:
    prof = p.profile(ctx.crop)
    if not prof or not ctx.soil or ctx.soil.ec_ds_m is None:
        return None
    limit, ec = prof["soil"]["ec_max"], ctx.soil.ec_ds_m
    if ec <= limit:
        return None
    return Alert(farm_id=ctx.farm_id, rule_id="soil.salinity_high", type=AlertType.soil,
                 severity=Severity.critical if ec > limit * 1.5 else Severity.warning,
                 title="ملوحة التربة مرتفعة", message=f"ملوحة التربة {ec} dS/m أعلى من حد تحمّل {ctx.crop}.",
                 reasons=[f"EC={ec} dS/m", f"حد التحمل المرجعي {limit} dS/m"],
                 action="راجع إجراءات غسيل الأملاح وتحسين الصرف.")


def disease_rule(ctx: FarmContext, p: CropProfiles, today: date) -> Alert | None:
    min_conf = p.defaults.get("disease_confidence_min", 0.7)
    confident = [d for d in ctx.diagnoses if d.confidence >= min_conf]
    if not confident:
        return None
    top = max(confident, key=lambda d: d.confidence)
    return Alert(farm_id=ctx.farm_id, rule_id=f"disease.detected.{top.label}", type=AlertType.disease,
                 severity=Severity.critical, title=f"اشتباه إصابة: {top.label}",
                 message=f"تحليل الصور رجّح إصابة {top.label} بثقة {top.confidence:.0%}.",
                 reasons=[f"ثقة النموذج {top.confidence:.0%}"] + ([f"الشدة: {top.severity}"] if top.severity else []),
                 action="افحص الحقل فورًا وابدأ إجراءات المكافحة المعتمدة.")


RULES = (irrigation_rule, fertilization_rule, soil_ph_rule, soil_salinity_rule, disease_rule)


def evaluate(ctx: FarmContext, profiles: CropProfiles, today: date | None = None) -> list[Alert]:
    today = today or date.today()
    alerts = [a for rule in RULES if (a := rule(ctx, profiles, today))]
    return sorted(alerts, key=lambda a: SEVERITY_ORDER[a.severity])
