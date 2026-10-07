import httpx
import pytest

from agri_rag.domain.farm import FarmContext, WeatherSnapshot
from agri_rag.domain.weather import OpenMeteoProvider, WeatherService, locate

PAYLOAD = {
    "current": {"time": "2026-10-04T12:00", "temperature_2m": 29.5, "relative_humidity_2m": 88},
    "hourly": {
        "time": [f"2026-10-0{d}T{h:02d}:00" for d in (3, 4, 5, 6) for h in range(24)],
        # 1 mm in the hour of 03 Oct 14:00 (past), 2 mm at 05 Oct 10:00 (ahead), 9 mm at 07 Oct (out of range -> absent)
        "precipitation": [1.0 if (d, h) == (3, 14) else 2.0 if (d, h) == (5, 10) else 0.0
                          for d in (3, 4, 5, 6) for h in range(24)],
    },
}


def provider(handler, **kw) -> OpenMeteoProvider:
    return OpenMeteoProvider(transport=httpx.MockTransport(handler), **kw)


async def test_parses_current_and_rain_windows():
    snap = await provider(lambda r: httpx.Response(200, json=PAYLOAD)).current(31.04, 31.38)
    assert (snap.temp_c, snap.humidity_pct) == (29.5, 88)
    assert snap.rain_mm_24h == 1.0 and snap.forecast_rain_mm_48h == 2.0
    assert snap.source == "open-meteo"


async def test_results_are_cached():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=PAYLOAD)

    p = provider(handler)
    await p.current(31.04, 31.38)
    await p.current(31.041, 31.381)  # same ~1 km cell
    assert len(calls) == 1


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500),
    lambda r: httpx.Response(200, json={"unexpected": True}),
    lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")),
])
async def test_failures_degrade_to_none(handler):
    assert await provider(handler).current(30.0, 31.0) is None


def test_locate_prefers_coordinates_then_governorate():
    assert locate(FarmContext(latitude=10.5, longitude=20.5, governorate="الدقهلية")) == (10.5, 20.5)
    assert locate(FarmContext(governorate="محافظة الدقهلية")) is not None
    assert locate(FarmContext(governorate="الإسكندرية")) == locate(FarmContext(governorate="الاسكندريه"))
    assert locate(FarmContext(governorate="مكان غير معروف")) is None
    assert locate(FarmContext()) is None


async def test_service_fills_weather_but_never_overrides_app_data():
    svc = WeatherService(provider(lambda r: httpx.Response(200, json=PAYLOAD)))
    filled = await svc.enrich(FarmContext(governorate="الدقهلية"))
    assert filled.weather.humidity_pct == 88

    mine = WeatherSnapshot(humidity_pct=40, source="sensor")
    kept = await svc.enrich(FarmContext(governorate="الدقهلية", weather=mine))
    assert kept.weather.humidity_pct == 40

    assert (await svc.enrich(None)) is None
    assert (await WeatherService(provider(lambda r: httpx.Response(500))).enrich(
        FarmContext(governorate="الدقهلية"))).weather is None


async def test_pipeline_puts_auto_weather_in_prompt(container):
    container.pipeline.weather = WeatherService(provider(lambda r: httpx.Response(200, json=PAYLOAD)))
    res = await container.pipeline.ask("الأرض مالحة أعمل إيه؟", farm=FarmContext(governorate="الدقهلية", crop="طماطم"))
    prompt = container.llm.calls[-1]["messages"][-1]["content"]
    assert "رطوبة %=88" in prompt and "خدمة طقس تلقائية" in prompt
    assert res.grounded


async def test_pipeline_survives_weather_outage(container):
    container.pipeline.weather = WeatherService(provider(lambda r: httpx.Response(503)))
    res = await container.pipeline.ask("الأرض مالحة أعمل إيه؟", farm=FarmContext(governorate="الدقهلية"))
    assert res.grounded and "الطقس" not in container.llm.calls[-1]["messages"][-1]["content"]
