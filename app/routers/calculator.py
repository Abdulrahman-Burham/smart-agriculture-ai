"""Agricultural Engineering Calculators Router: Tank-Mix Dosage & Salinity Advisor."""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from app.schemas.calculator import (
    FertilizerRequest,
    FertilizerResponse,
    SalinityRequest,
    SalinityResponse,
    SprayWindowRequest,
    SprayWindowResponse,
    TankMixRequest,
    TankMixResponse,
)
from app.services.agri_calculator_service import (
    calculate_fertilizer_needs,
    calculate_tank_mix,
    evaluate_spray_window,
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
        raise HTTPException(
            status_code=400, detail=f"خطأ في تقييم ملوحة المياه: {str(e)}"
        )


@router.post("/api/calculator/fertilizer", response_model=FertilizerResponse)
async def fertilizer_program_endpoint(payload: FertilizerRequest) -> FertilizerResponse:
    """Calculate crop N-P-K nutrient units, commercial 50kg bags, and growth stage feeding schedule."""
    try:
        return calculate_fertilizer_needs(payload)
    except Exception as e:
        logger.error(f"Fertilizer calculation error: {e}")
        raise HTTPException(
            status_code=400, detail=f"خطأ في حساب برنامج التسميد: {str(e)}"
        )


@router.post("/api/calculator/spray-window", response_model=SprayWindowResponse)
async def spray_weather_window_endpoint(payload: SprayWindowRequest) -> SprayWindowResponse:
    """Evaluate weather conditions for pesticide drift risk and safe spraying time window."""
    try:
        return evaluate_spray_window(payload)
    except Exception as e:
        logger.error(f"Spray window evaluation error: {e}")
        raise HTTPException(
            status_code=400, detail=f"خطأ في تقييم أمان وقت الرش: {str(e)}"
        )
