import os
import signal
import socket
import sys
import time
from threading import Event, Thread

import requests
from flask import Flask, jsonify

SERVICE_NAME = os.environ.get("SERVICE_NAME", "user-service")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "8001"))
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:5001")
INSTANCE_ID = socket.gethostname()
SERVICE_ADDRESS = os.environ.get(
    "SERVICE_ADDRESS", f"http://{INSTANCE_ID}:{SERVICE_PORT}"
)
HEARTBEAT_INTERVAL = 10  # seconds

app = Flask(__name__)
stop_event = Event()

@app.route("/ping")
def ping():
    return jsonify(
        {
            "status": "ok",
            "service": SERVICE_NAME,
            "instance": INSTANCE_ID,
            "address": SERVICE_ADDRESS,
        }
    )

@app.route("/hello")
def hello():
    return jsonify(
        {
            "message": f"Hello from {SERVICE_NAME}!",
            "instance": INSTANCE_ID,
            "address": SERVICE_ADDRESS,
        }
    )

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "instance": INSTANCE_ID})

def register(retry: bool = True) -> bool:
    payload = {"service": SERVICE_NAME, "address": SERVICE_ADDRESS}
    for attempt in range(1, 6):
        try:
            r = requests.post(
                f"{REGISTRY_URL}/register",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            if r.status_code in (200, 201):
                print(
                    f"[{SERVICE_NAME}:{INSTANCE_ID}] registered at {SERVICE_ADDRESS}",
                    flush=True,
                )
                return True
            print(
                f"[{SERVICE_NAME}:{INSTANCE_ID}] register failed ({r.status_code}): {r.text}",
                flush=True,
            )
        except requests.exceptions.RequestException as exc:
            print(
                f"[{SERVICE_NAME}:{INSTANCE_ID}] register attempt {attempt} error: {exc}",
                flush=True,
            )
        if not retry:
            return False
        time.sleep(2 * attempt)
    return False

def deregister() -> None:
    try:
        requests.post(
            f"{REGISTRY_URL}/deregister",
            json={"service": SERVICE_NAME, "address": SERVICE_ADDRESS},
            timeout=5,
        )
        print(f"[{SERVICE_NAME}:{INSTANCE_ID}] deregistered", flush=True)
    except requests.exceptions.RequestException as exc:
        print(f"[{SERVICE_NAME}:{INSTANCE_ID}] deregister error: {exc}", flush=True)

def _heartbeat_loop() -> None:
    while not stop_event.wait(HEARTBEAT_INTERVAL):
        try:
            r = requests.post(
                f"{REGISTRY_URL}/heartbeat",
                json={"service": SERVICE_NAME, "address": SERVICE_ADDRESS},
                timeout=5,
            )
            if r.status_code != 200:
                register(retry=False)
        except requests.exceptions.RequestException:
            pass

def _shutdown(sig, frame):  # noqa: D401
    print(f"\n[{SERVICE_NAME}:{INSTANCE_ID}] shutting down…", flush=True)
    stop_event.set()
    deregister()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    if not register():
        print(f"[{SERVICE_NAME}:{INSTANCE_ID}] could not reach registry — exiting", flush=True)
        sys.exit(1)

    Thread(target=_heartbeat_loop, daemon=True).start()

    print(
        f"[{SERVICE_NAME}:{INSTANCE_ID}] listening on 0.0.0.0:{SERVICE_PORT}",
        flush=True,
    )
    app.run(host="0.0.0.0", port=SERVICE_PORT, debug=False, use_reloader=False)
