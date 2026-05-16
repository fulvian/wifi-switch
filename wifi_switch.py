#!/usr/bin/env python3
"""WiFi auto-switch daemon. Monitors internet connectivity and switches
networks when the current one loses internet access."""

import subprocess
import time
import sys
from datetime import datetime

INTERFACE = "wlp194s0"
CHECK_URL = "http://connectivity-check.ubuntu.com"
CHECK_TIMEOUT = 5
CHECK_INTERVAL = 10
FAIL_THRESHOLD = 2
SUCCESS_THRESHOLD = 3
STABILIZE_WAIT = 15
NETWORKS = [
    "Ventura's Home_EXT",
    "Redmi 9A",
    "POCO X6 5G di Fulvio",
]


def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {level:<5} {msg}", flush=True)


def check_connectivity() -> bool:
    raise NotImplementedError


def get_available_networks() -> list[str]:
    raise NotImplementedError


def get_current_network() -> str:
    raise NotImplementedError


def switch_network(ssid: str) -> bool:
    raise NotImplementedError


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("INFO", "Interrotto dall'utente")
        sys.exit(0)
