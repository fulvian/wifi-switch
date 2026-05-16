# WiFi Auto-Switch Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python daemon that monitors internet connectivity on `wlp194s0` every 10s and automatically switches between three known WiFi networks based on actual HTTP reachability.

**Architecture:** Single Python script with four pure functions (check, scan, get_current, switch) orchestrated by a main loop that maintains failure/success counters and drives network switching. No external Python dependencies — stdlib only, delegates to `curl` and `nmcli` via subprocess.

**Tech Stack:** Python 3.12, subprocess (stdlib), unittest.mock (stdlib), pytest, systemd, nmcli 1.46, curl 8.5

---

## File Map

| File | Responsibility |
|------|---------------|
| `wifi_switch.py` | Daemon: connectivity check, network scan, switch logic, main loop |
| `tests/test_wifi_switch.py` | Unit tests for all four functions + state transitions |
| `wifi-switch.service` | systemd unit — runs daemon as root, auto-restart |
| `install.sh` | Copies binary, installs service, enables + starts it |

---

### Task 1: Test infrastructure and skeleton

**Files:**
- Create: `wifi_switch.py`
- Create: `tests/__init__.py`
- Create: `tests/test_wifi_switch.py`

- [ ] **Step 1: Install pytest**

```bash
pip install pytest --break-system-packages 2>/dev/null || pip install --user pytest
python3 -m pytest --version
```

Expected: `pytest 8.x.x`

- [ ] **Step 2: Create `wifi_switch.py` skeleton**

```python
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
```

- [ ] **Step 3: Create `tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `tests/test_wifi_switch.py` skeleton**

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock
import pytest
import wifi_switch as ws
```

- [ ] **Step 5: Verify pytest discovers the test file**

```bash
python3 -m pytest tests/ -v --collect-only
```

Expected output includes `tests/test_wifi_switch.py` with 0 tests collected, no errors.

- [ ] **Step 6: Commit**

```bash
git add wifi_switch.py tests/
git commit -m "feat: add daemon skeleton and test infrastructure"
```

---

### Task 2: check_connectivity()

**Files:**
- Modify: `wifi_switch.py` — implement `check_connectivity()`
- Modify: `tests/test_wifi_switch.py` — add `TestCheckConnectivity`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_wifi_switch.py`:

```python
class TestCheckConnectivity:
    def test_returns_true_when_curl_responds_200(self):
        mock = MagicMock(returncode=0, stdout="200")
        with patch("subprocess.run", return_value=mock):
            assert ws.check_connectivity() is True

    def test_returns_false_when_http_status_not_200(self):
        mock = MagicMock(returncode=0, stdout="000")
        with patch("subprocess.run", return_value=mock):
            assert ws.check_connectivity() is False

    def test_returns_false_when_curl_times_out(self):
        # curl returns non-zero on timeout (exit code 28)
        mock = MagicMock(returncode=28, stdout="")
        with patch("subprocess.run", return_value=mock):
            assert ws.check_connectivity() is False

    def test_returns_false_when_curl_cannot_resolve_dns(self):
        # curl returns 6 on DNS failure
        mock = MagicMock(returncode=6, stdout="")
        with patch("subprocess.run", return_value=mock):
            assert ws.check_connectivity() is False

    def test_calls_curl_with_correct_interface_and_timeout(self):
        mock = MagicMock(returncode=0, stdout="200")
        with patch("subprocess.run", return_value=mock) as mock_run:
            ws.check_connectivity()
        args = mock_run.call_args[0][0]
        assert "--interface" in args
        assert ws.INTERFACE in args
        assert "--max-time" in args
        assert str(ws.CHECK_TIMEOUT) in args
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_wifi_switch.py::TestCheckConnectivity -v
```

Expected: `FAILED` / `NotImplementedError` on all 5 tests.

- [ ] **Step 3: Implement `check_connectivity()`**

Replace `raise NotImplementedError` in `check_connectivity`:

```python
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
    return result.returncode == 0 and result.stdout.strip() == "200"
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_wifi_switch.py::TestCheckConnectivity -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add wifi_switch.py tests/test_wifi_switch.py
git commit -m "feat: implement check_connectivity with curl"
```

---

### Task 3: get_available_networks() and get_current_network()

**Files:**
- Modify: `wifi_switch.py` — implement both functions
- Modify: `tests/test_wifi_switch.py` — add two test classes

- [ ] **Step 1: Write failing tests**

Add to `tests/test_wifi_switch.py`:

```python
class TestGetAvailableNetworks:
    def test_parses_ssids_from_nmcli_output(self):
        mock = MagicMock(returncode=0, stdout="Ventura's Home_EXT\nRedmi 9A\n")
        with patch("subprocess.run", return_value=mock):
            result = ws.get_available_networks()
        assert result == ["Ventura's Home_EXT", "Redmi 9A"]

    def test_strips_whitespace_from_ssids(self):
        mock = MagicMock(returncode=0, stdout="  Redmi 9A  \n")
        with patch("subprocess.run", return_value=mock):
            result = ws.get_available_networks()
        assert result == ["Redmi 9A"]

    def test_skips_empty_lines(self):
        mock = MagicMock(returncode=0, stdout="Redmi 9A\n\n\n")
        with patch("subprocess.run", return_value=mock):
            result = ws.get_available_networks()
        assert result == ["Redmi 9A"]

    def test_returns_empty_list_on_nmcli_error(self):
        mock = MagicMock(returncode=1, stdout="")
        with patch("subprocess.run", return_value=mock):
            assert ws.get_available_networks() == []

    def test_calls_nmcli_with_correct_interface(self):
        mock = MagicMock(returncode=0, stdout="")
        with patch("subprocess.run", return_value=mock) as mock_run:
            ws.get_available_networks()
        args = mock_run.call_args[0][0]
        assert "nmcli" in args
        assert ws.INTERFACE in args


class TestGetCurrentNetwork:
    def test_returns_connected_ssid(self):
        mock = MagicMock(returncode=0, stdout="Ventura's Home_EXT\n")
        with patch("subprocess.run", return_value=mock):
            assert ws.get_current_network() == "Ventura's Home_EXT"

    def test_strips_trailing_newline(self):
        mock = MagicMock(returncode=0, stdout="Redmi 9A\n")
        with patch("subprocess.run", return_value=mock):
            assert ws.get_current_network() == "Redmi 9A"

    def test_returns_empty_string_on_nmcli_error(self):
        mock = MagicMock(returncode=1, stdout="")
        with patch("subprocess.run", return_value=mock):
            assert ws.get_current_network() == ""
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_wifi_switch.py::TestGetAvailableNetworks tests/test_wifi_switch.py::TestGetCurrentNetwork -v
```

Expected: `FAILED` / `NotImplementedError` on all 8 tests.

- [ ] **Step 3: Implement both functions**

Replace `raise NotImplementedError` in `get_available_networks`:

```python
def get_available_networks() -> list[str]:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list", "ifname", INTERFACE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
```

Replace `raise NotImplementedError` in `get_current_network`:

```python
def get_current_network() -> str:
    result = subprocess.run(
        ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", INTERFACE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_wifi_switch.py::TestGetAvailableNetworks tests/test_wifi_switch.py::TestGetCurrentNetwork -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add wifi_switch.py tests/test_wifi_switch.py
git commit -m "feat: implement get_available_networks and get_current_network"
```

---

### Task 4: switch_network()

**Files:**
- Modify: `wifi_switch.py` — implement `switch_network()`
- Modify: `tests/test_wifi_switch.py` — add `TestSwitchNetwork`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_wifi_switch.py`:

```python
class TestSwitchNetwork:
    def test_returns_true_on_successful_connect(self):
        mock = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock):
            assert ws.switch_network("Redmi 9A") is True

    def test_returns_false_when_nmcli_fails(self):
        mock = MagicMock(returncode=1)
        with patch("subprocess.run", return_value=mock):
            assert ws.switch_network("Redmi 9A") is False

    def test_calls_nmcli_with_ssid_and_interface(self):
        mock = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock) as mock_run:
            ws.switch_network("Redmi 9A")
        args = mock_run.call_args[0][0]
        assert "nmcli" in args
        assert "connect" in args
        assert "Redmi 9A" in args
        assert ws.INTERFACE in args
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_wifi_switch.py::TestSwitchNetwork -v
```

Expected: `FAILED` / `NotImplementedError` on all 3 tests.

- [ ] **Step 3: Implement `switch_network()`**

Replace `raise NotImplementedError` in `switch_network`:

```python
def switch_network(ssid: str) -> bool:
    result = subprocess.run(
        ["nmcli", "device", "wifi", "connect", ssid, "ifname", INTERFACE],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_wifi_switch.py::TestSwitchNetwork -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add wifi_switch.py tests/test_wifi_switch.py
git commit -m "feat: implement switch_network via nmcli"
```

---

### Task 5: main() loop

**Files:**
- Modify: `wifi_switch.py` — implement `main()`
- Modify: `tests/test_wifi_switch.py` — add `TestMainLoop`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_wifi_switch.py`:

```python
class TestMainLoop:
    """Tests run main() for a fixed number of iterations by raising
    StopIteration after N calls to time.sleep to break the infinite loop."""

    def _run_main(self, side_effects_check, side_effects_available,
                  side_effects_switch, current_network, iterations=1):
        """Helper: runs main() for `iterations` sleep calls then stops."""
        sleep_calls = []

        def fake_sleep(n):
            sleep_calls.append(n)
            if len(sleep_calls) >= iterations:
                raise StopIteration

        with patch("wifi_switch.get_current_network", return_value=current_network), \
             patch("wifi_switch.check_connectivity", side_effect=side_effects_check), \
             patch("wifi_switch.get_available_networks", side_effect=side_effects_available), \
             patch("wifi_switch.switch_network", side_effect=side_effects_switch), \
             patch("time.sleep", side_effect=fake_sleep):
            try:
                ws.main()
            except StopIteration:
                pass
        return sleep_calls

    def test_switches_down_after_fail_threshold(self):
        # 2 failures → switch to Redmi 9A
        sleep_calls = self._run_main(
            side_effects_check=[False, False],
            side_effects_available=[["Redmi 9A"], ["Redmi 9A"]],
            side_effects_switch=[True],
            current_network="Ventura's Home_EXT",
            iterations=3,  # 2 CHECK_INTERVAL sleeps + 1 STABILIZE_WAIT sleep
        )
        # third sleep is STABILIZE_WAIT (15), not CHECK_INTERVAL (10)
        assert ws.STABILIZE_WAIT in sleep_calls

    def test_does_not_switch_before_fail_threshold(self):
        # only 1 failure → no switch
        with patch("wifi_switch.get_current_network", return_value="Ventura's Home_EXT"), \
             patch("wifi_switch.check_connectivity", return_value=False), \
             patch("wifi_switch.switch_network") as mock_switch, \
             patch("time.sleep", side_effect=[None, StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        mock_switch.assert_not_called()

    def test_switches_up_after_success_threshold(self):
        # on Redmi 9A, 3 successes with Ventura in range → switch up
        sleep_calls = self._run_main(
            side_effects_check=[True, True, True],
            side_effects_available=[
                ["Ventura's Home_EXT", "Redmi 9A"],
                ["Ventura's Home_EXT", "Redmi 9A"],
                ["Ventura's Home_EXT", "Redmi 9A"],
            ],
            side_effects_switch=[True],
            current_network="Redmi 9A",
            iterations=4,
        )
        assert ws.STABILIZE_WAIT in sleep_calls

    def test_does_not_switch_up_if_better_not_in_range(self):
        # on Redmi 9A, 3 successes but Ventura NOT in scan → no switch
        with patch("wifi_switch.get_current_network", return_value="Redmi 9A"), \
             patch("wifi_switch.check_connectivity", return_value=True), \
             patch("wifi_switch.get_available_networks", return_value=["Redmi 9A"]), \
             patch("wifi_switch.switch_network") as mock_switch, \
             patch("time.sleep", side_effect=[None, None, None, StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        mock_switch.assert_not_called()

    def test_skips_unavailable_fallback_and_tries_next(self):
        # Ventura fails, Redmi NOT in scan → should try POCO X6
        with patch("wifi_switch.get_current_network", return_value="Ventura's Home_EXT"), \
             patch("wifi_switch.check_connectivity", return_value=False), \
             patch("wifi_switch.get_available_networks",
                   return_value=["POCO X6 5G di Fulvio"]), \
             patch("wifi_switch.switch_network") as mock_switch, \
             patch("time.sleep", side_effect=[None, None, StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        mock_switch.assert_called_once_with("POCO X6 5G di Fulvio")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_wifi_switch.py::TestMainLoop -v
```

Expected: `FAILED` / `NotImplementedError` on all 5 tests.

- [ ] **Step 3: Implement `main()`**

Replace `raise NotImplementedError` in `main`:

```python
def main() -> None:
    current = get_current_network()
    log("INFO", f"Avviato su {current!r}")

    failure_count = 0
    success_count = 0

    while True:
        ok = check_connectivity()

        try:
            current_idx = NETWORKS.index(current)
        except ValueError:
            current_idx = len(NETWORKS)

        if ok:
            failure_count = 0
            success_count += 1
            log("INFO", f"Connettività OK su {current!r} (success #{success_count})")

            if current_idx > 0:
                available = get_available_networks()
                better = next(
                    (n for n in NETWORKS[:current_idx] if n in available), None
                )
                if better and success_count >= SUCCESS_THRESHOLD:
                    log("INFO",
                        f"Success #{success_count} su {current!r} — "
                        f"{better!r} in range, switch up")
                    if switch_network(better):
                        current = better
                        log("INFO", f"Connesso a {current!r} — monitoraggio attivo")
                    else:
                        log("ERROR", f"nmcli connect a {better!r} fallito")
                    failure_count = 0
                    success_count = 0
                    time.sleep(STABILIZE_WAIT)
                    continue

        else:
            success_count = 0
            failure_count += 1
            log("WARN", f"Fail #{failure_count} su {current!r}")

            if failure_count >= FAIL_THRESHOLD:
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
                    success_count = 0
                    time.sleep(STABILIZE_WAIT)
                    continue
                else:
                    log("ERROR", "Nessuna rete fallback disponibile")

        time.sleep(CHECK_INTERVAL)
```

- [ ] **Step 4: Run all tests — verify they all pass**

```bash
python3 -m pytest tests/ -v
```

Expected: `21 passed`

- [ ] **Step 5: Commit**

```bash
git add wifi_switch.py tests/test_wifi_switch.py
git commit -m "feat: implement main loop with state machine"
```

---

### Task 6: systemd service file

**Files:**
- Create: `wifi-switch.service`

- [ ] **Step 1: Create `wifi-switch.service`**

```ini
[Unit]
Description=WiFi Network Auto-Switch Daemon
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=/usr/local/bin/wifi-switch
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Verify syntax**

```bash
systemd-analyze verify wifi-switch.service 2>&1 || true
```

Expected: no errors (warnings about missing binary path are OK at this stage).

- [ ] **Step 3: Commit**

```bash
git add wifi-switch.service
git commit -m "feat: add systemd service unit"
```

---

### Task 7: install.sh

**Files:**
- Create: `install.sh`

- [ ] **Step 1: Create `install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY=/usr/local/bin/wifi-switch
SERVICE=/etc/systemd/system/wifi-switch.service

echo "Installing wifi-switch..."

# Copy daemon (shebang already present in wifi_switch.py)
sudo install -m 755 "$SCRIPT_DIR/wifi_switch.py" "$BINARY"

# Install service
sudo install -m 644 "$SCRIPT_DIR/wifi-switch.service" "$SERVICE"

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable wifi-switch
sudo systemctl restart wifi-switch

echo "Done. Check status with: journalctl -u wifi-switch -f"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x install.sh
```

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "feat: add install script"
```

---

### Task 8: Install and verify

- [ ] **Step 1: Run full test suite one last time**

```bash
python3 -m pytest tests/ -v
```

Expected: `21 passed`, `0 failed`

- [ ] **Step 2: Run daemon in foreground to verify basic operation**

```bash
python3 wifi_switch.py
```

Expected: log line like:
```
[2026-05-16 10:15:33] INFO  Avviato su "Ventura's Home_EXT"
[2026-05-16 10:15:43] INFO  Connettività OK su "Ventura's Home_EXT" (success #1)
```

Kill with Ctrl+C after confirming first check cycle completes.

- [ ] **Step 3: Install as systemd service**

```bash
bash install.sh
```

Expected output ends with:
```
Done. Check status with: journalctl -u wifi-switch -f
```

- [ ] **Step 4: Verify service is running**

```bash
systemctl status wifi-switch
```

Expected: `active (running)`

- [ ] **Step 5: Tail logs and confirm first check cycle**

```bash
journalctl -u wifi-switch -f --no-pager
```

Wait for at least 2 check cycles (20s). Expected log lines:
```
INFO  Avviato su "Ventura's Home_EXT"
INFO  Connettività OK su "Ventura's Home_EXT" (success #1)
INFO  Connettività OK su "Ventura's Home_EXT" (success #2)
```

Ctrl+C to exit log tail.

- [ ] **Step 6: Simulate failure with iptables**

In terminal 1 (watch logs):
```bash
journalctl -u wifi-switch -f --no-pager
```

In terminal 2 (block outbound WiFi):
```bash
sudo iptables -I OUTPUT -o wlp194s0 -j DROP
```

Expected in logs within 30s:
```
WARN  Fail #1 su "Ventura's Home_EXT"
WARN  Fail #2 — switch a "Redmi 9A"
INFO  Connesso a "Redmi 9A" — monitoraggio attivo
```

- [ ] **Step 7: Restore and verify auto-return**

```bash
sudo iptables -D OUTPUT -o wlp194s0 -j DROP
```

Expected in logs within 60s (3 successes × 10s + stabilize):
```
INFO  Connettività OK su "Redmi 9A" (success #3)
INFO  Success #3 su "Redmi 9A" — "Ventura's Home_EXT" in range, switch up
INFO  Connesso a "Ventura's Home_EXT" — monitoraggio attivo
```

- [ ] **Step 8: Final commit**

```bash
git add -A
git status  # verify nothing unexpected
git commit -m "chore: finalize wifi-switch daemon — all tests pass, service verified"
```
