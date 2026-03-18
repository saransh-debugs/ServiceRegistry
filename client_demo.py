import argparse
import random
import sys
from collections import Counter
from typing import Dict, List, Optional
import requests

def discover(registry_url: str, service: str) -> List[Dict]:
    try:
        r = requests.get(f"{registry_url}/discover/{service}", timeout=5)
    except requests.exceptions.RequestException as exc:
        print(f"[client] cannot reach registry at {registry_url}: {exc}")
        sys.exit(1)

    if r.status_code == 404:
        print(f"[client] service '{service}' not found in registry")
        sys.exit(1)

    if r.status_code != 200:
        print(f"[client] discovery error {r.status_code}: {r.text}")
        sys.exit(1)

    data = r.json()
    instances = data.get("instances", [])
    if not instances:
        print(f"[client] no active instances found for '{service}'")
        sys.exit(1)

    return instances


def call_instance(address: str) -> Optional[Dict]:
    try:
        r = requests.get(f"{address}/ping", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as exc:
        print(f"[client] call to {address} failed: {exc}")
        return None


def run_demo(registry_url: str, service: str, num_calls: int) -> None:  # noqa: D103
    print("=" * 60)
    print("SERVICE DISCOVERY CLIENT DEMO")
    print("=" * 60)
    print(f"Registry : {registry_url}")
    print(f"Service  : {service}")
    print(f"Calls    : {num_calls}")
    print()

    instances = discover(registry_url, service)
    addresses = [inst["address"] for inst in instances]

    print(f"Discovered {len(addresses)} instance(s):")
    for addr in addresses:
        print(f"  {addr}")
    print()

    hit_counter: Counter[str] = Counter()
    print(f"Making {num_calls} calls with random instance selection:\n")

    for i in range(1, num_calls + 1):
        chosen = random.choice(addresses)
        result = call_instance(chosen)
        if result:
            instance_id = result.get("instance", chosen)
            hit_counter[instance_id] += 1
            print(f"  Call {i:>2}: -> {chosen}  (instance: {instance_id})")
        else:
            print(f"  Call {i:>2}: -> {chosen}  (ERROR)")

    # --- distribution tally ---
    print()
    print("Distribution:")
    total = sum(hit_counter.values())
    for inst_id, count in hit_counter.most_common():
        bar = "#" * count
        pct = count / total * 100 if total else 0
        print(f"  {inst_id:<30} {count:>3} calls  {pct:5.1f}%  {bar}")
    print()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Service discovery demo client")
    parser.add_argument("--service", default="user-service", help="Service name to discover")
    parser.add_argument("--calls", type=int, default=10, help="Number of calls to make")
    parser.add_argument("--registry", default="http://localhost:5001", help="Registry base URL")
    args = parser.parse_args()

    run_demo(args.registry, args.service, args.calls)
