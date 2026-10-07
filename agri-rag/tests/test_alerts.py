from datetime import date

from agri_rag.alerts.rules import CropProfiles, evaluate
from agri_rag.config import Settings
from agri_rag.domain.farm import FarmContext, IrrigationMethod, SoilReport, VisionDiagnosis, WeatherSnapshot

PROFILES = CropProfiles.load(Settings().crop_profiles_path)
TODAY = date(2026, 9, 30)


def farm(**kw) -> FarmContext:
    base = dict(farm_id="f1", crop="طماطم", growth_stage="إزهار", irrigation_method=IrrigationMethod.drip)
    return FarmContext(**{**base, **kw})


def ids(alerts):
    return [a.rule_id for a in alerts]


def test_irrigation_due_and_critical_when_very_overdue():
    alerts = evaluate(farm(last_irrigation_date=date(2026, 9, 24)), PROFILES, TODAY)  # 6 days vs interval 2
    assert alerts[0].rule_id == "irrigation.due" and alerts[0].severity.value == "critical"


def test_irrigation_postponed_when_rain_forecast():
    w = WeatherSnapshot(forecast_rain_mm_48h=12)
    alerts = evaluate(farm(last_irrigation_date=date(2026, 9, 27), weather=w), PROFILES, TODAY)
    assert ids(alerts) == ["irrigation.postpone_rain"]


def test_heat_shortens_interval():
    f = farm(last_irrigation_date=date(2026, 9, 28), weather=WeatherSnapshot(temp_c=38))  # 2 days, interval 2->1
    assert "irrigation.due" in ids(evaluate(f, PROFILES, TODAY))
    f.weather = WeatherSnapshot(temp_c=25)
    assert "irrigation.due" in ids(evaluate(f, PROFILES, TODAY))  # exactly at interval
    f.last_irrigation_date = date(2026, 9, 29)
    assert not evaluate(f, PROFILES, TODAY)


def test_soil_and_disease_rules():
    f = farm(soil=SoilReport(ph=8.0, ec_ds_m=4.5),
             diagnoses=[VisionDiagnosis(label="اللفحة المتأخرة", confidence=0.91),
                        VisionDiagnosis(label="صدأ", confidence=0.3)])
    got = ids(evaluate(f, PROFILES, TODAY))
    assert {"soil.ph_out_of_range", "soil.salinity_high", "disease.detected.اللفحة المتأخرة"} <= set(got)
    assert not any("صدأ" in i for i in got)  # low-confidence diagnosis must not alert


def test_missing_data_raises_no_false_alerts():
    assert evaluate(FarmContext(farm_id="x"), PROFILES, TODAY) == []
