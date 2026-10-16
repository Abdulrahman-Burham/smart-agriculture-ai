from app.services.agri_calculator_service import (
    calculate_tank_mix,
    evaluate_water_salinity,
)
from app.services.audio_service import (
    normalize_to_egyptian_dialect,
    synthesize_speech,
    to_spoken_egyptian_arabic,
    transcribe_speech,
)
from app.services.cv_service import ComputerVisionService
from app.services.llm_service import (
    IRRIG_TO_ENUM,
    KNOWN_AGRI_RAG_CROPS,
    format_agri_rag_sources,
    get_gemini_key_pool_and_model,
    get_rag_pipeline,
    load_oauth_config,
    query_agri_rag,
    save_oauth_config,
)
from app.services.telemetry_service import (
    collect_server_system_metrics,
    format_uptime_ar,
)
from app.services.vision_service import (
    MAX_UPLOAD_BYTES,
    get_cv_classifier,
    verify_plant_image_gemini_sync,
)
from app.services.weather_service import (
    EGYPT_GOV_COORDS,
    calculate_agronomic_disease_risks,
    fetch_weather_forecast,
    get_public_platform_stats,
    nearest_governorate,
)

__all__ = [
    "transcribe_speech",
    "synthesize_speech",
    "normalize_to_egyptian_dialect",
    "to_spoken_egyptian_arabic",
    "ComputerVisionService",
    "get_gemini_key_pool_and_model",
    "query_agri_rag",
    "get_rag_pipeline",
    "format_agri_rag_sources",
    "load_oauth_config",
    "save_oauth_config",
    "KNOWN_AGRI_RAG_CROPS",
    "IRRIG_TO_ENUM",
    "get_cv_classifier",
    "verify_plant_image_gemini_sync",
    "MAX_UPLOAD_BYTES",
    "fetch_weather_forecast",
    "calculate_agronomic_disease_risks",
    "get_public_platform_stats",
    "nearest_governorate",
    "EGYPT_GOV_COORDS",
    "collect_server_system_metrics",
    "format_uptime_ar",
    "calculate_tank_mix",
    "evaluate_water_salinity",
]
