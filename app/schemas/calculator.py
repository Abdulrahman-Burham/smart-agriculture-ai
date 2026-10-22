"""Pydantic Schemas for Tank-Mix Dosage Calculator & Water Salinity Advisor."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ─── Tank-Mix Dosage Schemas ───────────────────────────────────────────────


class TankMixRequest(BaseModel):
    mode: str = Field(
        "area",
        description="area (حساب لمساحة معينة) or tank (حساب لملء تانك/رشاشة مباشرة)",
    )
    area_value: float = Field(
        1.0,
        gt=0,
        description="Area quantity, e.g. 1.0, 2, 10 (used when mode == 'area')",
    )
    area_unit: str = Field(
        "feddan",
        description="feddan (فدان), qirat (قيراط), sahm (سهم), or sqm (متر مربع)",
    )
    tank_type: str = Field(
        "knapsack_20l",
        description="knapsack_20l, knapsack_16l, motor_600l, motor_300l, motor_200l, motor_100l, or drip_1000l",
    )
    tanks_count: int = Field(
        1,
        ge=1,
        description="Number of tanks to fill (used when mode == 'tank')",
    )
    dosage_rate: float = Field(
        ...,
        gt=0,
        description="Recommended dosage rate (e.g. 250 g/feddan, 200 ml/100L, 250 g/barrel)",
    )
    dosage_unit: str = Field(
        "per_feddan",
        description="per_feddan (لكل فدان), per_100l (لكل 100 لتر ماء), per_200l (لكل برميل 200 لتر), or per_tank (لكل تانك/رشاشة مباشرة)",
    )
    chemical_type: str = Field(
        "powder",
        description="powder (بودرة/مسحوق بالجرام) or liquid (سائل بالمل/سم³)",
    )
    crop_category: str = Field(
        "vegetable",
        description="vegetable (خضر ومحاصيل حقلية) or orchard (أشجار وبساتين)",
    )
    product_name: Optional[str] = Field(
        "", description="Commercial or active ingredient name"
    )
    mix_partners: Optional[List[str]] = Field(
        default_factory=list,
        description="Other chemicals planned in same tank to check compatibility",
    )


class TankMixResponse(BaseModel):
    status: str = "success"
    area_feddan: float = Field(..., description="Normalized area in feddans")
    area_display: str = Field(
        ..., description="Human-readable area description in Arabic"
    )
    tank_capacity_liters: float = Field(
        ..., description="Capacity of chosen spray tank"
    )
    total_water_liters: float = Field(
        ..., description="Total water volume needed to spray area"
    )
    total_chemical_amount: float = Field(
        ..., description="Total chemical quantity required"
    )
    chemical_unit: str = Field(..., description="جرام or مل/سم³")
    amount_per_tank: float = Field(
        ..., description="Exact dose to put in each full tank"
    )
    amount_per_tank_practical: str = Field(
        ..., description="Practical farmer scoop approximation, e.g. 2.5 ملاعق طعام"
    )
    tanks_count_exact: float = Field(..., description="Exact number of tank fills")
    tanks_count_practical: int = Field(
        ..., description="Practical rounded number of tanks"
    )
    compatibility_warnings: List[str] = Field(
        default_factory=list, description="Tank-mix chemical incompatibility cautions"
    )
    instructions_ar: List[str] = Field(
        default_factory=list, description="Step-by-step mixing and safety instructions"
    )


# ─── Salinity & Water Quality Schemas ──────────────────────────────────────


class SalinityRequest(BaseModel):
    salinity_value: float = Field(..., gt=0, description="Measured salinity reading")
    salinity_unit: str = Field("ppm", description="ppm (TDS) or ec (dS/m)")
    crop_name: str = Field(
        "طماطم",
        description="Egyptian crop name, e.g. طماطم, بطاطس, قمح, زيتون, نخيل, مانجو",
    )
    irrigation_method: str = Field(
        "تنقيط", description="تنقيط (Drip), غمر (Flood), or رشاشات (Sprinkler)"
    )


class SalinityResponse(BaseModel):
    status: str = "success"
    crop_name: str
    tds_ppm: float = Field(..., description="Total dissolved solids in ppm")
    ec_dsm: float = Field(..., description="Electrical conductivity in dS/m")
    water_quality_grade: str = Field(
        ...,
        description="عذبة ممتازة, مقبولة, متوسطة الملوحة, شديدة الملوحة, or فائقة الملوحة",
    )
    water_quality_color: str = Field(..., description="Hex color badge for UI")
    crop_tolerance_threshold_ppm: float = Field(
        ..., description="Threshold salinity where yield starts dropping"
    )
    crop_tolerance_threshold_ec: float = Field(..., description="Threshold EC in dS/m")
    yield_potential_percent: float = Field(
        ..., description="Estimated crop productivity %"
    )
    is_critical_risk: bool = Field(
        ..., description="Whether salinity causes severe leaf scorch or root death"
    )
    evaluation_ar: str = Field(
        ...,
        description="Detailed agronomic evaluation text in Egyptian agricultural Arabic",
    )
    alleviation_protocol: List[str] = Field(
        default_factory=list, description="Practical soil/water mitigation treatments"
    )


# ─── Fertilizer Program & NPK Commercial Bag Schemas ───────────────────────


class FertilizerRequest(BaseModel):
    crop_name: str = Field(
        "بطاطس",
        description="Egyptian crop name, e.g. طماطم, بطاطس, قمح, ذرة, مانجو, بصل, فراولة",
    )
    area_value: float = Field(
        1.0, gt=0, description="Area quantity, e.g. 1.0, 5, 12"
    )
    area_unit: str = Field(
        "feddan", description="feddan (فدان) or qirat (قيراط)"
    )
    soil_type: str = Field(
        "clay_old",
        description="clay_old (أرض طينية / وادي ودلتا) or sandy_new (أرض رملية / استصلاح جديد)",
    )
    irrigation_method: str = Field(
        "drip", description="drip (تنقيط) or flood (غمر)"
    )
    nitrogen_source: str = Field(
        "nitrate",
        description="nitrate (نترات نشادر 33.5%), urea (يوريا 46.5%), or sulfate (سلفات نشادر 20.6%)",
    )
    phosphorus_source: str = Field(
        "single_super",
        description="single_super (سوبر فوسفات عادي 15.5%), triple_super (تريبل فوسفات 46%), or phosphoric_acid (حمض فوسفوريك 85%)",
    )
    potassium_source: str = Field(
        "sulfate",
        description="sulfate (سلفات بوتاسيوم 50%) or nitrate_potassium (نترات بوتاسيوم 46%)",
    )


class FertilizerStagePlan(BaseModel):
    stage_name_ar: str = Field(..., description="اسم مرحلة نمو النبات")
    stage_timing_ar: str = Field(..., description="التوقيت ومرحلة عمر النبات")
    n_percentage: float = Field(..., description="نسبة الأزوت المخصصة لهذه المرحلة %")
    p_percentage: float = Field(..., description="نسبة الفوسفور المخصصة لهذه المرحلة %")
    k_percentage: float = Field(..., description="نسبة البوتاسيوم المخصصة لهذه المرحلة %")
    recommendations_ar: List[str] = Field(
        default_factory=list, description="توصيات التسميد والري العملية لهذه المرحلة"
    )


class FertilizerResponse(BaseModel):
    status: str = "success"
    crop_name: str
    area_feddan: float
    area_display: str
    soil_type_ar: str
    irrigation_method_ar: str
    total_n_units: float = Field(..., description="إجمالي وحدات الأزوت N الصافية المطلوبة")
    total_p_units: float = Field(..., description="إجمالي وحدات الفوسفور P2O5 المطلوبة")
    total_k_units: float = Field(..., description="إجمالي وحدات البوتاسيوم K2O المطلوبة")
    nitrogen_fertilizer_name: str
    nitrogen_bags_50kg: float = Field(..., description="عدد شكاير 50 كجم سماد أزوتي")
    nitrogen_total_kg: float = Field(..., description="إجمالي الوزن بالكيلوجرام")
    phosphorus_fertilizer_name: str
    phosphorus_bags_50kg: float = Field(..., description="عدد شكاير 50 كجم سماد فوسفاتي أو لترات")
    phosphorus_total_kg: float
    potassium_fertilizer_name: str
    potassium_bags_50kg: float = Field(..., description="عدد شكاير 50 كجم سماد بوتاسي")
    potassium_total_kg: float
    growth_stages_schedule: List[FertilizerStagePlan] = Field(
        default_factory=list, description="جدول توزيع الدفعات السمادية على مراحل النمو"
    )
    compatibility_and_soil_cautions: List[str] = Field(
        default_factory=list, description="محاذير الخلط والتسميد الهامة لحماية النبات والشبكة"
    )


# ─── Spray Weather Window & Drift Risk Schemas ─────────────────────────────


class SprayWindowRequest(BaseModel):
    governorate: str = Field("الدقهلية", description="اسم المحافظة لجلب الطقس الحي")
    temperature_c: Optional[float] = Field(None, description="درجة الحرارة المئوية (يدوي اختياري)")
    wind_speed_kmh: Optional[float] = Field(None, description="سرعة الرياح كم/س (يدوي اختياري)")
    humidity_pct: Optional[float] = Field(None, description="الرطوبة النسبية % (يدوي اختياري)")
    rain_prob_pct: Optional[float] = Field(0.0, description="احتمالية سقوط أمطار %")
    chemical_category: str = Field(
        "fungicide_systemic",
        description="fungicide_systemic (فطري جهازي), insecticide_contact (حشري ملامسة), herbicide_selective (حشائش اختياري), foliar_fertilizer (مغذيات ورقية)",
    )


class SprayWindowResponse(BaseModel):
    status: str = "success"
    governorate: str
    safety_code: str = Field(..., description="ideal (مثالي), caution (بحذر), danger (ممنوع)")
    safety_label_ar: str
    safety_badge_color: str
    temperature_c: float
    wind_speed_kmh: float
    humidity_pct: float
    rain_prob_pct: float
    drift_risk_level: str
    evaporation_scorch_risk: str
    rain_wash_risk: str
    optimal_time_window_ar: str
    field_rules_ar: List[str] = Field(default_factory=list)
