# wifi-switch LLM Wiki — Log

## 2026-07-02 — INGEST wiki bootstrap + switching policy rework

Detail: Reworked switching from fixed-hierarchy auto-return to sticky-current + cooldown. Root cause of user pain: the deployed binary still ran the old switch-up logic that forced return to the unstable home network (`Ventura's Home_EXT`), overriding manual choices. Changes: re-sync `current` from `nmcli` each loop; removed switch-up; added `COOLDOWN_S=300` per-network cooldown and `pick_fallback()` (considers all in-scan networks, cooldown-aware); fixed `write_wifi_state()` to create `/run/texbot` (was ENOENT every cycle once deployed). Reinstalled + restarted the systemd service. Commits: `c22975f` (policy) + follow-up fix. Pages: [[index]], [[switching-policy]].
