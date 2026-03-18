import sys
from collections import Counter
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

import client_demo

def _mock_response(status_code: int, json_body: dict) -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_body
    m.text = str(json_body)
    m.raise_for_status = MagicMock()
    return m

INSTANCES = [
    {"address": "http://svc-1:8001", "uptime_seconds": 30.0},
    {"address": "http://svc-2:8001", "uptime_seconds": 25.0},
]

DISCOVER_OK = _mock_response(200, {"service": "user-service", "instances": INSTANCES, "count": 2})
DISCOVER_404 = _mock_response(404, {"message": "not found"})
PING_RESP = _mock_response(200, {"status": "ok", "service": "user-service", "instance": "svc-1"})

def test_discover_returns_instance_list():
    with patch("client_demo.requests.get", return_value=DISCOVER_OK):
        result = client_demo.discover("http://registry:5001", "user-service")
    assert len(result) == 2
    assert result[0]["address"] == "http://svc-1:8001"

def test_discover_404_exits():
    with patch("client_demo.requests.get", return_value=DISCOVER_404):
        with pytest.raises(SystemExit):
            client_demo.discover("http://registry:5001", "user-service")

def test_discover_connection_error_exits():
    import requests as req
    with patch("client_demo.requests.get", side_effect=req.exceptions.ConnectionError):
        with pytest.raises(SystemExit):
            client_demo.discover("http://registry:5001", "user-service")

def test_discover_empty_instances_exits():
    resp = _mock_response(200, {"service": "user-service", "instances": [], "count": 0})
    with patch("client_demo.requests.get", return_value=resp):
        with pytest.raises(SystemExit):
            client_demo.discover("http://registry:5001", "user-service")

def test_call_instance_returns_json():
    with patch("client_demo.requests.get", return_value=PING_RESP):
        result = client_demo.call_instance("http://svc-1:8001")
    assert result["instance"] == "svc-1"

def test_call_instance_connection_error_returns_none():
    import requests as req
    with patch("client_demo.requests.get", side_effect=req.exceptions.ConnectionError):
        result = client_demo.call_instance("http://svc-1:8001")
    assert result is None

def test_run_demo_calls_correct_number_of_times(capsys):
    ping_responses = [
        _mock_response(200, {"status": "ok", "service": "user-service", "instance": f"inst-{i % 2}"})
        for i in range(6)
    ]

    def fake_get(url, **kwargs):
        if "/discover/" in url:
            return DISCOVER_OK
        return ping_responses.pop(0)

    with patch("client_demo.requests.get", side_effect=fake_get):
        client_demo.run_demo("http://registry:5001", "user-service", num_calls=6)

    captured = capsys.readouterr().out
    # Each call line should appear
    for i in range(1, 7):
        assert f"Call {i:>2}:" in captured
    assert "Distribution:" in captured


def test_run_demo_random_choice_selects_from_instances():
    seen_populations = []
    original_choice = __import__("random").choice
    def capturing_choice(population):
        seen_populations.append(list(population))
        return population[0]
    ping_resp = _mock_response(200, {"status": "ok", "service": "user-service", "instance": "inst-0"})
    def fake_get(url, **kwargs):
        if "/discover/" in url:
            return DISCOVER_OK
        return ping_resp

    with patch("client_demo.requests.get", side_effect=fake_get), \
         patch("client_demo.random.choice", side_effect=capturing_choice):
        client_demo.run_demo("http://registry:5001", "user-service", num_calls=3)

    expected = sorted(inst["address"] for inst in INSTANCES)
    for pop in seen_populations:
        assert sorted(pop) == expected
