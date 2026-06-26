#!/usr/bin/env python3
"""WiFi auto-switch daemon. Monitors internet connectivity and switches
networks when the current one loses internet access."""

import subprocess
import time
import sys
import json
import os
from datetime import datetime

INTERFACE = "wlp194s0"
CHECK_URL = "http://connectivity-check.ubuntu.com"
CHECK_TIMEOUT = 5
CHECK_INTERVAL = 10
FAIL_THRESHOLD = 2
STABILIZE_WAIT = 15
FREEZE_TTL_S = 30.0
NET_STATE_PATH = "/run/texbot/net_state.json"
NETWORKS = [
    "Ventura's Home_EXT",
    "Redmi 9A",
    "POCO X6 5G di Fulvio",
]


def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {level:<5} {msg}", flush=True)


def check_connectivity() -> bool:
    result = subprocess.run(
        [
            "curl",
            "--interface", INTERFACE,
            "--max-time", str(CHECK_TIMEOUT),
            "-s", "-o", "/dev/null",
            "-w", "%{http_code}",
            CHECK_URL,
        ],
        capture_output=True,
        text=True,
    )
    code = result.stdout.strip()
    return result.returncode == 0 and code in ("200", "204")


def get_available_networks() -> list[str]:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list", "ifname", INTERFACE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_current_network() -> str:
    result = subprocess.run(
        ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", INTERFACE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def switch_network(ssid: str) -> bool:
    result = subprocess.run(
        ["nmcli", "device", "wifi", "connect", ssid, "ifname", INTERFACE],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def read_net_state_file(path: str = NET_STATE_PATH) -> dict | None:
    """Load the coordination flag; None if missing/unreadable."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def is_freeze_active(state: dict | None) -> bool:
    """FROZEN flag within TTL blocks switching."""
    if not state:
        return False
    if state.get("owner") != "texbot":
        return False
    if state.get("mode") != "FROZEN":
        return False
    ts = state.get("ts")
    if ts is None:
        return False
    now = time.time()
    return (now - ts) < FREEZE_TTL_S


def write_wifi_state(ssid: str, path: str = NET_STATE_PATH) -> None:
    """Publish our current stable state for the bot's re-entry gate."""
    try:
        existing = read_net_state_file(path) or {}
        existing["wifi"] = {
            "state": f"stable-on:{ssid}",
            "ts": time.time(),
        }
        # Atomic write (write to tmp, then rename) to avoid partial reads
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(existing, f)
        os.replace(tmp, path)
    except OSError as e:
        log("ERROR", f"write_wifi_state failed: {e}")


def main() -> None:
    current = get_current_network()
    log("INFO", f"Avviato su {current!r}")

    failure_count = 0

    while True:
        ok = check_connectivity()
        state = read_net_state_file()
        frozen = is_freeze_active(state)

        try:
            current_idx = NETWORKS.index(current)
        except ValueError:
            current_idx = len(NETWORKS)

        if ok:
            failure_count = 0
            log("INFO", f"Connettività OK su {current!r}")
            # NO switch-up logic. Stay on current unless it fails.

        else:
            failure_count += 1
            log("WARN", f"Fail #{failure_count} su {current!r}")

            if failure_count >= FAIL_THRESHOLD and not frozen:
                available = get_available_networks()
                candidates = NETWORKS[current_idx + 1:] if current_idx < len(NETWORKS) else NETWORKS
                target = next((n for n in candidates if n in available), None)
                if target:
                    log("WARN",
                        f"Fail #{failure_count} — switch a {target!r}")
                    if switch_network(target):
                        current = target
                        log("INFO", f"Connesso a {current!r} — monitoraggio attivo")
                    else:
                        log("ERROR", f"nmcli connect a {target!r} fallito")
                    failure_count = 0
                    time.sleep(STABILIZE_WAIT)
                    write_wifi_state(current)
                    continue
                else:
                    log("ERROR", "Nessuna rete fallback disponibile")
            elif frozen:
                log("INFO", "FROZEN flag active; skipping switch")

        write_wifi_state(current)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("INFO", "Interrotto dall'utente")
        sys.exit(0)
