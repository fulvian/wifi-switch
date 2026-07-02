---
title: "Network Switching Policy"
kind: architecture
status: active
created: 2026-07-02
last_updated: 2026-07-02
sources:
  - wifi_switch.py (read 2026-07-02)
tags: [wifi, failover, policy, cooldown, networkmanager]
confidence: high
cross_refs:
  - "[[index]]"
---

# Network Switching Policy

How `main()` decides when and where to switch. This is the project's core non-obvious behavior — the code shows the mechanics; this page records the *why*.

## Design intent

The original spec assumed a fixed priority hierarchy where the home network (`Ventura's Home_EXT`) is always best and the daemon should auto-return to it (3 consecutive successes → "switch up"). In practice **home is the most unstable link**: it stays associated but loses internet. The auto-return dragged the user off a stable phone hotspot back onto the flaky home network repeatedly, fighting the user's manual choice.

Policy was inverted to **stability-first**: stay on whatever currently works; only move on real failure; never return home just because it reappeared.

## Rules (as implemented)

1. **Re-sync each loop.** `main()` calls `get_current_network()` at the top of every cycle. If the live SSID differs from tracked `current` (user switched manually, or NM autoconnected), adopt it and reset `failure_count`. → the daemon never drags the user off a network they chose.
2. **No switch-up.** There is no proactive move to a higher-priority network. A "better" network is only ever a *candidate* when the current one fails. Once on a working network, the daemon stays.
3. **Switch only on real failure.** After `FAIL_THRESHOLD` (2) consecutive connectivity failures, and only if not frozen, pick a fallback.
4. **Cooldown.** On failure the current network is stamped into a `cooldown` dict for `COOLDOWN_S` (300s). `pick_fallback()` skips networks still in cooldown → prevents flapping straight back onto the network that just died.
5. **Upward recovery.** `pick_fallback()` considers *all* in-scan known networks except current (not just lower-priority ones), so the daemon can recover from the lowest network back up to a higher one that now works.
6. **Fallback ordering.** Among candidates in scan: prefer those NOT in cooldown, iterated in `NETWORKS` priority order (Ventura > Redmi > POCO). If every candidate is in cooldown, pick the one whose cooldown expires soonest (failed longest ago) — being on something beats a dead link.

## Freeze coordination

`is_freeze_active()` gates switching: a `{"owner":"texbot","mode":"FROZEN","ts":...}` entry in `/run/texbot/net_state.json` within `FREEZE_TTL_S` (30s) blocks any switch. The daemon publishes its own `wifi.state = stable-on:<ssid>` back to that file each loop via `write_wifi_state()` (atomic tmp+rename; creates `/run/texbot` if missing).

## Chosen policy variant (2026-07-02)

Among the return-to-home options, the active choice is **never auto-return to home** — home is treated as an ordinary cooldown-gated candidate that is only tried when the current network fails. Alternative variants considered but not implemented: return-home-only-if-proven-stable-for-a-long-window; adaptive least-recently-failed ordering. Revisit if metered-data cost on phone hotspots becomes the dominant concern.

## Key constants

| Constant | Value | Meaning |
|---|---|---|
| `CHECK_INTERVAL` | 10s | loop period |
| `FAIL_THRESHOLD` | 2 | consecutive fails before switching |
| `STABILIZE_WAIT` | 15s | pause after a switch before resuming checks |
| `COOLDOWN_S` | 300s | avoid re-selecting a just-failed network |
| `FREEZE_TTL_S` | 30s | max age of a respected freeze-flag |
