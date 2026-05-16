# WiFi Auto-Switch Daemon — Design Spec

**Date:** 2026-05-16  
**Status:** Approved

## Problem

Single WiFi adapter (`wlp194s0`) on Linux. Primary network stays associated but loses internet bandwidth without disconnecting. NM does not auto-switch to a known backup network in this case. Remote SSH sessions (via Tailscale) block until manual intervention.

## Requirements

- Monitor actual internet connectivity every 10s via HTTP check (not ping)
- Switch to fallback network after 2 consecutive failures
- Auto-return to higher-priority network after 3 consecutive successes
- Support 3-network hierarchy with priority order
- Run as systemd service, restart on crash

## Network Hierarchy

| Priority | SSID | Availability |
|----------|------|--------------|
| 0 (highest) | `Ventura's Home_EXT` | Home WiFi |
| 1 | `Redmi 9A` | Always-on hotspot |
| 2 (lowest) | `POCO X6 5G di Fulvio` | Manual hotspot |

## Architecture

Three pure functions + one main loop. No external Python dependencies.

```
ConnectivityChecker  →  curl --interface wlp194s0 --max-time 5
NetworkSwitcher      →  nmcli device wifi connect / list
WifiSwitchDaemon     →  10s loop, manages fail/success counters, state
```

### State Machine

```
STABLE ──(2 consecutive fail)──► SWITCHING_DOWN ──(nmcli ok)──► STABLE (lower net)
  ▲                                                                      │
  │                                                         (3 consecutive success)
  └──────────────────────── SWITCHING_UP ◄──────────────────────────────┘
```

## Configuration (constants in script header)

```python
INTERFACE        = "wlp194s0"
CHECK_URL        = "http://connectivity-check.ubuntu.com"
CHECK_TIMEOUT    = 5    # seconds
CHECK_INTERVAL   = 10   # seconds
FAIL_THRESHOLD   = 2    # consecutive failures before switch down
SUCCESS_THRESHOLD = 3   # consecutive successes before switch up
STABILIZE_WAIT   = 15   # seconds to wait after nmcli connect before resuming checks
NETWORKS = [
    "Ventura's Home_EXT",
    "Redmi 9A",
    "POCO X6 5G di Fulvio",
]
```

## Data Flow

`current_network` is tracked in daemon state. On startup, read from `nmcli -g GENERAL.CONNECTION device show wlp194s0`. Updated on every successful switch. If current SSID not in NETWORKS list, treat as priority = len(NETWORKS) (worst).

```
every 10s:
  result = check_connectivity()
  current_idx = NETWORKS.index(current_network)  # 0=best, 2=worst

  if fail:
    failure_count++; success_count = 0
    if failure_count >= FAIL_THRESHOLD:
      available = get_available_networks()
      # iterate NETWORKS[current_idx+1:] — lower priority, higher index
      target = first SSID in NETWORKS[current_idx+1:] that is in available
      if target: switch_network(target); sleep(STABILIZE_WAIT); reset counters

  if success:
    success_count++; failure_count = 0
    if current_idx > 0:  # not already on primary
      available = get_available_networks()
      # iterate NETWORKS[0:current_idx] — higher priority, lower index
      better = first SSID in NETWORKS[0:current_idx] that is in available
      if better: switch_network(better); sleep(STABILIZE_WAIT); reset counters
```

## Edge Cases

| Case | Behavior |
|------|----------|
| nmcli connect fails | Log error, retry next cycle |
| All fallbacks unavailable | Stay on current, keep monitoring |
| POCO X6 not in scan | Skipped automatically (not in available list) |
| During stabilize wait | Checks paused, no state changes |
| Daemon crash | systemd `Restart=always`, back in 5s |

## Code Structure

```
wifi-switch/
├── wifi_switch.py       # daemon (~150 lines, stdlib only)
├── wifi-switch.service  # systemd unit
└── install.sh           # installs to /usr/local/bin, enables service
```

### wifi_switch.py skeleton

```python
def check_connectivity() -> bool:
    # subprocess curl --interface INTERFACE --max-time CHECK_TIMEOUT
    # returns True if HTTP 200, False otherwise

def get_available_networks() -> list[str]:
    # nmcli -t -f SSID device wifi list ifname INTERFACE
    # returns list of SSIDs currently in scan

def switch_network(ssid: str) -> bool:
    # nmcli device wifi connect SSID ifname INTERFACE
    # returns True on success

def main():
    # infinite loop: check, update counters, switch if needed
    # log all state transitions to stdout (→ journald)
```

### wifi-switch.service

```ini
[Unit]
Description=WiFi Network Auto-Switch Daemon
After=network.target NetworkManager.service

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

## Logging Format

```
[2026-05-16 10:15:33] INFO  Connettività OK su Ventura's Home_EXT
[2026-05-16 10:17:03] WARN  Fail #1 su Ventura's Home_EXT
[2026-05-16 10:17:13] WARN  Fail #2 — switch a Redmi 9A
[2026-05-16 10:17:28] INFO  Connesso a Redmi 9A — monitoraggio attivo
[2026-05-16 10:22:28] INFO  Success #3 su Redmi 9A — Ventura's Home_EXT in range, switch up
[2026-05-16 10:22:43] INFO  Connesso a Ventura's Home_EXT — monitoraggio attivo
```

## Testing

**Manual (foreground):**
```bash
python3 wifi_switch.py
# simulate failure:
sudo iptables -I OUTPUT -o wlp194s0 -j DROP
# restore:
sudo iptables -D OUTPUT -o wlp194s0 -j DROP
```

**Post-install monitoring:**
```bash
journalctl -u wifi-switch -f
```

## Installation

```bash
bash install.sh
```
