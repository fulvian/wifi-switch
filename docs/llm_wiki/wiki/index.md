---
title: "wifi-switch LLM Wiki — Index"
kind: architecture
status: active
created: 2026-07-02
last_updated: 2026-07-02
sources:
  - wifi_switch.py (read 2026-07-02)
  - wifi-switch.service (read 2026-07-02)
tags: [index, wifi, daemon, networkmanager]
confidence: high
cross_refs:
  - "[[switching-policy]]"
  - "[[log]]"
---

# wifi-switch LLM Wiki — Index

## Purpose

Single-adapter WiFi failover daemon for `wlp194s0`. Monitors real internet reachability (HTTP, not ping) and switches between known networks when the current one loses connectivity. Runs as a systemd service. `wifi_switch.py` is stdlib-only, delegating to `curl` and `nmcli` via subprocess.

## Architecture

```
check_connectivity()   → curl --interface wlp194s0 --max-time 5  (HTTP 200/204 = up)
get_current_network()  → nmcli -g GENERAL.CONNECTION device show wlp194s0
get_available_networks → nmcli -t -f SSID device wifi list ifname wlp194s0
switch_network(ssid)   → nmcli device wifi connect <ssid> ifname wlp194s0
pick_fallback(...)     → choose next network on failure (cooldown-aware)
main()                 → 10s loop: re-sync current, check, switch-on-fail, publish state
```

Networks (priority order, used only as a tie-break, NOT for auto-return):
`Ventura's Home_EXT` (home, unmetered, unstable) → `Redmi 9A` → `POCO X6 5G di Fulvio` (phone hotspots).

Coordination: reads `/run/texbot/net_state.json` for a `FROZEN` freeze-flag (texbot owner, 30s TTL) that blocks switching, and publishes its own `stable-on:<ssid>` state to the same file.

## Pages

| Page | Kind | Status |
|---|---|---|
| [[switching-policy]] | architecture | active |
| [[log]] | — | active |

## Current status

Switching policy reworked 2026-07-02 (commits `c22975f`, follow-up `/run/texbot` fix): **sticky-current + cooldown, no forced return to home**. Previously the daemon forced the user back to the unstable home network via switch-up logic; that is removed. See [[switching-policy]].
