import json

import pytest
from fastapi.testclient import TestClient

from agri_rag.api.app import create_app


@pytest.fixture()
def client(container):
    return TestClient(create_app(container))


def test_health(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["chunks"] > 0


def test_chat_json(client):
    r = client.post("/v1/chat", json={"question": "الأرض مالحة أعمل إيه؟"})
    body = r.json()
    assert r.status_code == 200 and body["grounded"] and body["sources"] and body["session_id"]


def test_chat_validation(client):
    assert client.post("/v1/chat", json={"question": ""}).status_code == 422


def test_sse_stream_event_order(client):
    with client.stream("POST", "/v1/chat/stream", json={"question": "الأرض مالحة أعمل إيه؟"}) as r:
        raw = "".join(r.iter_text())
    events = [line.split(": ", 1)[1] for line in raw.splitlines() if line.startswith("event: ")]
    assert events[0] == "sources" and events[-1] == "done" and "token" in events
    done = json.loads(raw.strip().splitlines()[-1].split("data: ", 1)[1])
    assert "timings" in done


def test_alerts_endpoint(client):
    r = client.post("/v1/alerts/evaluate", json={"farm": {
        "farm_id": "f1", "crop": "قمح", "growth_stage": "تفريع", "irrigation_method": "surface",
        "last_irrigation_date": "2020-01-01"}})
    assert r.status_code == 200 and r.json()["alerts"][0]["type"] == "irrigation"


def test_api_key_enforced(container):
    container.settings.api_key = "secret"
    c = TestClient(create_app(container))
    assert c.post("/v1/chat", json={"question": "مرحبا"}).status_code == 401
    ok = c.post("/v1/chat", json={"question": "الأرض مالحة"}, headers={"X-API-Key": "secret"})
    assert ok.status_code == 200
