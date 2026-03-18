
import importlib
import os
import sys

import pytest


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SERVICE_NAME", "test-service")
    monkeypatch.setenv("SERVICE_PORT", "8001")
    monkeypatch.setenv("SERVICE_ADDRESS", "http://test-host:8001")
    monkeypatch.setenv("REGISTRY_URL", "http://fake-registry:5001")

    if "microservice" in sys.modules:
        del sys.modules["microservice"]
    mod = importlib.import_module("microservice")
    mod.app.config["TESTING"] = True
    with mod.app.test_client() as c:
        yield c

def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "healthy"

def test_health_includes_instance(client):
    body = client.get("/health").get_json()
    assert "instance" in body

def test_ping_returns_ok(client):
    r = client.get("/ping")
    assert r.status_code == 200

def test_ping_body_fields(client):
    body = client.get("/ping").get_json()
    assert body["service"] == "test-service"
    assert body["address"] == "http://test-host:8001"
    assert "instance" in body
    assert body["status"] == "ok"

def test_hello_returns_ok(client):
    assert client.get("/hello").status_code == 200

def test_hello_body_fields(client):
    body = client.get("/hello").get_json()
    assert "message" in body
    assert "test-service" in body["message"]
    assert "instance" in body
