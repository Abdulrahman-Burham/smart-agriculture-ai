"""Agricultural Engineering Calculators Router: Tank-Mix Dosage & Salinity Advisor."""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from app.schemas.calculator import (
    SalinityRequest,
    SalinityResponse,
    TankMixRequest,
    TankMixResponse,
)
from app.services.agri_calculator_service import (
    calculate_tank_mix,
    evaluate_water_salinity,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agricultural Calculators"])


@router.post("/api/calculator/tank-mix", response_model=TankMixResponse)
async def tank_mix_calculator_endpoint(payload: TankMixRequest) -> TankMixResponse:
    """Calculate exact spray tank refills, scoop quantities, and chemical compatibility."""
    try:
        return calculate_tank_mix(payload)
    except Exception as e:
        logger.error(f"Tank-mix calculation error: {e}")
        raise HTTPException(status_code=400, detail=f"خطأ في حساب جرعة الرش: {str(e)}")


@router.post("/api/calculator/salinity", response_model=SalinityResponse)
async def water_salinity_advisor_endpoint(payload: SalinityRequest) -> SalinityResponse:
    """Evaluate irrigation water EC/TDS, calculate crop yield loss %, and generate mitigation plan."""
    try:
        return evaluate_water_salinity(payload)
    except Exception as e:
        logger.error(f"Salinity evaluation error: {e}")
        raise HTTPException(status_code=400, detail=f"خطأ في تقييم ملوحة المياه: {str(e)}")
