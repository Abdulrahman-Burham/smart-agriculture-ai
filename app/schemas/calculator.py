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
