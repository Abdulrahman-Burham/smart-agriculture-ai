"""Farm context: the structured data the OCR and Vision modules hand to the assistant.

These models are the integration contract between the three AI components. The Vision
engineer emits `VisionDiagnosis`, the OCR engineer emits `SoilReport`, the backend adds
weather/operations data, and the assistant turns all of it into grounded advice.
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

LOW_CONFIDENCE = 0.6


class IrrigationMethod(str, Enum):
    drip = "drip"  # تنقيط
    surface = "surface"  # غمر
    sprinkler = "sprinkler"  # رش


_METHOD_AR = {"drip": "تنقيط", "surface": "غمر", "sprinkler": "رش"}


class SoilReport(BaseModel):
    ph: float | None = Field(None, ge=0, le=14)
    ec_ds_m: float | None = Field(None, ge=0, description="Electrical conductivity, dS/m")
    nitrogen_ppm: float | None = Field(None, ge=0)
    phosphorus_ppm: float | None = Field(None, ge=0)
    potassium_ppm: float | None = Field(None, ge=0)
    organic_matter_pct: float | None = Field(None, ge=0, le=100)
    texture: str | None = Field(None, description="e.g. رملية / طينية / طميية")
    sampled_at: date | None = None


class VisionDiagnosis(BaseModel):
    label: str = Field(description="Class name from the vision model, e.g. 'اللفحة المتأخرة'")
    confidence: float = Field(ge=0, le=1)
    crop: str | None = None
    severity: str | None = None


class WeatherSnapshot(BaseModel):
    temp_c: float | None = None
    humidity_pct: float | None = Field(None, ge=0, le=100)
    rain_mm_24h: float | None = Field(None, ge=0)
    forecast_rain_mm_48h: float | None = Field(None, ge=0)
    source: str | None = Field(None, description="e.g. 'sensor', 'open-meteo'")
    observed_at: str | None = None


class FarmContext(BaseModel):
    farm_id: str = "unknown"
    farmer_name: str | None = None
    governorate: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90, description="Farm location; enables automatic weather")
    longitude: float | None = Field(None, ge=-180, le=180)
    crop: str | None = None
    growth_stage: str | None = None
    area_feddan: float | None = Field(None, gt=0)
    irrigation_method: IrrigationMethod | None = None
    last_irrigation_date: date | None = None
    last_fertilization_date: date | None = None
    soil: SoilReport | None = None
    diagnoses: list[VisionDiagnosis] = Field(default_factory=list)
    weather: WeatherSnapshot | None = None
    memory_notes: str | None = None

    def render_arabic(self) -> str:
        """Compact Arabic rendering injected into the prompt (kept short to protect latency)."""
        lines: list[str] = []
        head = [("اسم المزارع", self.farmer_name), ("المحافظة", self.governorate), ("المحصول", self.crop),
                ("مرحلة النمو", self.growth_stage), ("المساحة (فدان)", self.area_feddan),
                ("طريقة الري", _METHOD_AR.get(self.irrigation_method.value) if self.irrigation_method else None),
                ("آخر ري", self.last_irrigation_date), ("آخر تسميد", self.last_fertilization_date)]
        lines += [f"- {k}: {v}" for k, v in head if v is not None]
        if self.soil:
            s = self.soil
            parts = [("pH", s.ph), ("الملوحة EC (dS/m)", s.ec_ds_m), ("نيتروجين ppm", s.nitrogen_ppm),
                     ("فوسفور ppm", s.phosphorus_ppm), ("بوتاسيوم ppm", s.potassium_ppm),
                     ("مادة عضوية %", s.organic_matter_pct), ("القوام", s.texture), ("تاريخ العينة", s.sampled_at)]
            lines.append("- تحليل التربة: " + "، ".join(f"{k}={v}" for k, v in parts if v is not None))
        for d in self.diagnoses:
            flag = " (ثقة منخفضة - غير مؤكد)" if d.confidence < LOW_CONFIDENCE else ""
            sev = f"، الشدة: {d.severity}" if d.severity else ""
            lines.append(f"- تشخيص الصورة: {d.label} بثقة {d.confidence:.0%}{sev}{flag}")
        if self.weather:
            w = self.weather
            parts = [("حرارة °م", w.temp_c), ("رطوبة %", w.humidity_pct), ("أمطار 24س (مم)", w.rain_mm_24h),
                     ("متوقع أمطار 48س (مم)", w.forecast_rain_mm_48h),
                     ("مصدر القراءة", {"open-meteo": "خدمة طقس تلقائية"}.get(w.source or "", w.source))]
            lines.append("- الطقس: " + "، ".join(f"{k}={v}" for k, v in parts if v is not None))
        if self.memory_notes:
            lines.append(f"- سجل وذاكرة المزارع السابقة:\n{self.memory_notes}")
        return "\n".join(lines)

    def is_empty(self) -> bool:
        return not self.render_arabic()

    def today_delta(self, d: date | None, today: date) -> int | None:
        return (today - d).days if d else None
