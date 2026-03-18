import importlib
import sys
import pytest

@pytest.fixture()
def client():
    """Return a Flask test client with an empty registry."""
    # Re-import the module each time so the in-memory registry is clean
    if "service_registry_improved" in sys.modules:
        del sys.modules["service_registry_improved"]
    mod = importlib.import_module("service_registry_improved")
    mod.app.config["TESTING"] = True
    with mod.app.test_client() as c:
        yield c

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "healthy"

def test_register_new_service(client):
    r = client.post("/register", json={"service": "svc-a", "address": "http://host:8001"})
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "registered"

def test_register_duplicate_updates_heartbeat(client):
    client.post("/register", json={"service": "svc-a", "address": "http://host:8001"})
    r = client.post("/register", json={"service": "svc-a", "address": "http://host:8001"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "updated"

def test_register_missing_fields_returns_400(client):
    r = client.post("/register", json={"service": "svc-a"})  # no address
    assert r.status_code == 400

def test_register_empty_body_returns_400(client):
    r = client.post("/register", json={})
    assert r.status_code == 400

def test_discover_known_service(client):
    client.post("/register", json={"service": "svc-a", "address": "http://host:8001"})
    r = client.get("/discover/svc-a")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 1
    assert body["instances"][0]["address"] == "http://host:8001"


def test_discover_multiple_instances(client):
    for port in (8001, 8002):
        client.post("/register", json={"service": "svc-a", "address": f"http://host:{port}"})
    r = client.get("/discover/svc-a")
    assert r.get_json()["count"] == 2


def test_discover_unknown_service_returns_404(client):
    r = client.get("/discover/nonexistent")
    assert r.status_code == 404

def test_heartbeat_updates_registered_instance(client):
    client.post("/register", json={"service": "svc-a", "address": "http://host:8001"})
    r = client.post("/heartbeat", json={"service": "svc-a", "address": "http://host:8001"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_heartbeat_unknown_service_returns_404(client):
    r = client.post("/heartbeat", json={"service": "ghost", "address": "http://host:8001"})
    assert r.status_code == 404


def test_heartbeat_unknown_instance_returns_404(client):
    client.post("/register", json={"service": "svc-a", "address": "http://host:8001"})
    r = client.post("/heartbeat", json={"service": "svc-a", "address": "http://host:9999"})
    assert r.status_code == 404

def test_deregister_removes_instance(client):
    client.post("/register", json={"service": "svc-a", "address": "http://host:8001"})
    r = client.post("/deregister", json={"service": "svc-a", "address": "http://host:8001"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "deregistered"
    # Service key removed when no instances remain
    r2 = client.get("/discover/svc-a")
    assert r2.status_code == 404


def test_deregister_unknown_service_returns_404(client):
    r = client.post("/deregister", json={"service": "ghost", "address": "http://host:8001"})
    assert r.status_code == 404

def test_deregister_one_instance_leaves_other(client):
    for port in (8001, 8002):
        client.post("/register", json={"service": "svc-a", "address": f"http://host:{port}"})
    client.post("/deregister", json={"service": "svc-a", "address": "http://host:8001"})
    body = client.get("/discover/svc-a").get_json()
    assert body["count"] == 1
    assert body["instances"][0]["address"] == "http://host:8002"

def test_list_services_empty(client):
    r = client.get("/services")
    assert r.status_code == 200
    assert r.get_json()["total_services"] == 0

def test_list_services_counts_correctly(client):
    client.post("/register", json={"service": "svc-a", "address": "http://host:8001"})
    client.post("/register", json={"service": "svc-a", "address": "http://host:8002"})
    client.post("/register", json={"service": "svc-b", "address": "http://host:9001"})
    body = client.get("/services").get_json()
    assert body["total_services"] == 2
    assert body["services"]["svc-a"]["active_instances"] == 2
    assert body["services"]["svc-b"]["active_instances"] == 1
