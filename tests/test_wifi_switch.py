import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock, mock_open
import pytest
import time
import json
import tempfile
import wifi_switch as ws


class TestCheckConnectivity:
    def test_returns_true_when_curl_responds_200(self):
        mock = MagicMock(returncode=0, stdout="200")
        with patch("subprocess.run", return_value=mock):
            assert ws.check_connectivity() is True

    def test_returns_true_when_curl_responds_204(self):
        # connectivity-check.ubuntu.com returns 204, not 200
        mock = MagicMock(returncode=0, stdout="204")
        with patch("subprocess.run", return_value=mock):
            assert ws.check_connectivity() is True

    def test_returns_false_when_http_status_not_200_or_204(self):
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
        with patch("wifi_switch.get_current_network", return_value="Ventura's Home_EXT"), \
             patch("wifi_switch.check_connectivity", side_effect=[False, False]), \
             patch("wifi_switch.read_net_state_file", return_value=None), \
             patch("wifi_switch.get_available_networks", side_effect=[["Redmi 9A"], ["Redmi 9A"]]), \
             patch("wifi_switch.switch_network", return_value=True) as mock_switch, \
             patch("wifi_switch.write_wifi_state"), \
             patch("time.sleep", side_effect=[None, None, StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        mock_switch.assert_called_once()

    def test_does_not_switch_before_fail_threshold(self):
        # only 1 failure → no switch
        with patch("wifi_switch.get_current_network", return_value="Ventura's Home_EXT"), \
             patch("wifi_switch.check_connectivity", return_value=False), \
             patch("wifi_switch.read_net_state_file", return_value=None), \
             patch("wifi_switch.switch_network") as mock_switch, \
             patch("wifi_switch.write_wifi_state"), \
             patch("time.sleep", side_effect=[StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        mock_switch.assert_not_called()

    def test_skips_unavailable_fallback_and_tries_next(self):
        # Ventura fails, Redmi NOT in scan → should try POCO X6
        with patch("wifi_switch.get_current_network", return_value="Ventura's Home_EXT"), \
             patch("wifi_switch.check_connectivity", return_value=False), \
             patch("wifi_switch.read_net_state_file", return_value=None), \
             patch("wifi_switch.get_available_networks",
                   return_value=["POCO X6 5G di Fulvio"]), \
             patch("wifi_switch.switch_network") as mock_switch, \
             patch("wifi_switch.write_wifi_state"), \
             patch("time.sleep", side_effect=[None, None, StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        mock_switch.assert_called_once_with("POCO X6 5G di Fulvio")

    def test_sticky_failover_never_switches_up(self):
        """Once on a network with internet, stay. Never switch to 'better' network."""
        # Current: "Redmi 9A" (working); available: "Ventura's Home_EXT" (preferred, ranked first)
        with patch("wifi_switch.get_current_network", return_value="Redmi 9A"), \
             patch("wifi_switch.check_connectivity", return_value=True), \
             patch("wifi_switch.get_available_networks",
                   return_value=["Ventura's Home_EXT", "Redmi 9A"]), \
             patch("wifi_switch.switch_network") as mock_switch, \
             patch("wifi_switch.write_wifi_state"), \
             patch("time.sleep", side_effect=[StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        # Must NOT call switch_network (no switch-UP logic)
        mock_switch.assert_not_called()

    def test_freeze_flag_prevents_switch(self):
        """FROZEN flag (fresh, within TTL) blocks any switch action."""
        fresh_ts = time.time()
        frozen_state = {"owner": "texbot", "mode": "FROZEN", "ts": fresh_ts}

        with patch("wifi_switch.get_current_network", return_value="Redmi 9A"), \
             patch("wifi_switch.check_connectivity", return_value=False), \
             patch("wifi_switch.get_available_networks", return_value=["POCO X6 5G di Fulvio"]), \
             patch("wifi_switch.read_net_state_file", return_value=frozen_state), \
             patch("wifi_switch.switch_network") as mock_switch, \
             patch("wifi_switch.write_wifi_state"), \
             patch("time.sleep", side_effect=[None, StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        # Must NOT call switch (freeze active)
        mock_switch.assert_not_called()

    def test_stale_freeze_flag_allows_switch(self):
        """Stale FROZEN flag (past TTL) does NOT block switching."""
        old_ts = time.time() - 35.0  # 35s old, past 30s TTL
        stale_frozen = {"owner": "texbot", "mode": "FROZEN", "ts": old_ts}

        with patch("wifi_switch.get_current_network", return_value="Redmi 9A"), \
             patch("wifi_switch.check_connectivity", return_value=False), \
             patch("wifi_switch.get_available_networks", return_value=["POCO X6 5G di Fulvio"]), \
             patch("wifi_switch.read_net_state_file", return_value=stale_frozen), \
             patch("wifi_switch.switch_network", return_value=True) as mock_switch, \
             patch("wifi_switch.write_wifi_state"), \
             patch("time.sleep", side_effect=[None, None, StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        # Must call switch (stale flag does not block)
        mock_switch.assert_called_once()

    def test_publishes_wifi_state_on_each_iteration(self):
        """After each iteration, publish own state (stable-on:<ssid>)."""
        with patch("wifi_switch.get_current_network", return_value="Redmi 9A"), \
             patch("wifi_switch.check_connectivity", return_value=True), \
             patch("wifi_switch.read_net_state_file", return_value=None), \
             patch("wifi_switch.write_wifi_state") as mock_write, \
             patch("time.sleep", side_effect=[StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        # Must call write_wifi_state at least once with current ssid
        mock_write.assert_called()
        # Check that it was called with the current network
        call_args = mock_write.call_args
        assert call_args is not None
        assert call_args[0][0] == "Redmi 9A"


class TestPickFallback:
    NOW = 1000.0

    def test_returns_none_when_no_other_network_available(self):
        assert ws.pick_fallback(
            "Ventura's Home_EXT", ["Ventura's Home_EXT"], {}, self.NOW
        ) is None

    def test_excludes_current_network(self):
        # only current in scan → nothing to switch to
        assert ws.pick_fallback("Redmi 9A", ["Redmi 9A"], {}, self.NOW) is None

    def test_prefers_priority_order_among_fresh(self):
        # both fresh → Ventura (idx 0) wins over Redmi (idx 1)
        result = ws.pick_fallback(
            "POCO X6 5G di Fulvio",
            ["Ventura's Home_EXT", "Redmi 9A"],
            {},
            self.NOW,
        )
        assert result == "Ventura's Home_EXT"

    def test_skips_network_in_cooldown(self):
        # Ventura in cooldown → pick next fresh (Redmi)
        result = ws.pick_fallback(
            "POCO X6 5G di Fulvio",
            ["Ventura's Home_EXT", "Redmi 9A"],
            {"Ventura's Home_EXT": self.NOW + 100},
            self.NOW,
        )
        assert result == "Redmi 9A"

    def test_expired_cooldown_is_fresh_again(self):
        result = ws.pick_fallback(
            "POCO X6 5G di Fulvio",
            ["Ventura's Home_EXT"],
            {"Ventura's Home_EXT": self.NOW - 1},
            self.NOW,
        )
        assert result == "Ventura's Home_EXT"

    def test_all_in_cooldown_picks_soonest_to_expire(self):
        # both cooling down → pick the one that failed longest ago (soonest expiry)
        result = ws.pick_fallback(
            "POCO X6 5G di Fulvio",
            ["Ventura's Home_EXT", "Redmi 9A"],
            {"Ventura's Home_EXT": self.NOW + 200, "Redmi 9A": self.NOW + 50},
            self.NOW,
        )
        assert result == "Redmi 9A"

    def test_recovers_upward_from_lowest_network(self):
        # on lowest-priority POCO, it fails → can still reach higher networks
        result = ws.pick_fallback(
            "POCO X6 5G di Fulvio",
            ["Redmi 9A", "POCO X6 5G di Fulvio"],
            {},
            self.NOW,
        )
        assert result == "Redmi 9A"


class TestMainManualAndCooldown:
    def test_adopts_manual_switch_and_does_not_leave_it(self):
        """User manually on POCO; daemon started thinking Ventura. One transient
        failure must not drag them off POCO before FAIL_THRESHOLD, and re-sync
        must adopt POCO as current."""
        with patch("wifi_switch.get_current_network",
                   return_value="POCO X6 5G di Fulvio"), \
             patch("wifi_switch.check_connectivity", return_value=True), \
             patch("wifi_switch.read_net_state_file", return_value=None), \
             patch("wifi_switch.switch_network") as mock_switch, \
             patch("wifi_switch.write_wifi_state") as mock_write, \
             patch("time.sleep", side_effect=[StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        mock_switch.assert_not_called()
        assert mock_write.call_args[0][0] == "POCO X6 5G di Fulvio"

    def test_failed_network_goes_into_cooldown_not_reselected(self):
        """Ventura fails → switch to Redmi. When Redmi later fails, Ventura is
        still in cooldown so POCO is chosen instead of flapping back to Ventura."""
        # get_current_network reflects the daemon's own switches via a sequence:
        # start=Ventura, loop1..2=Ventura, after switch loop3=Redmi, loop4=Redmi
        current_seq = [
            "Ventura's Home_EXT",  # startup read
            "Ventura's Home_EXT",  # loop1 re-sync
            "Ventura's Home_EXT",  # loop2 re-sync
            "Redmi 9A",            # loop3 re-sync (adopts daemon switch)
            "Redmi 9A",            # loop4 re-sync
        ]
        with patch("wifi_switch.get_current_network", side_effect=current_seq), \
             patch("wifi_switch.check_connectivity",
                   side_effect=[False, False, False, False]), \
             patch("wifi_switch.read_net_state_file", return_value=None), \
             patch("wifi_switch.get_available_networks",
                   return_value=["Ventura's Home_EXT", "Redmi 9A", "POCO X6 5G di Fulvio"]), \
             patch("wifi_switch.switch_network", return_value=True) as mock_switch, \
             patch("wifi_switch.write_wifi_state"), \
             patch("time.sleep", side_effect=[None, None, None, StopIteration()]):
            try:
                ws.main()
            except StopIteration:
                pass
        targets = [c[0][0] for c in mock_switch.call_args_list]
        assert targets == ["Redmi 9A", "POCO X6 5G di Fulvio"]


class TestReadNetStateFile:
    def test_returns_dict_when_file_exists(self):
        data = {"owner": "texbot", "mode": "FROZEN", "ts": 123.45}
        with patch("builtins.open", mock_open(read_data=json.dumps(data))):
            result = ws.read_net_state_file("/fake/path.json")
        assert result == data

    def test_returns_none_when_file_missing(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = ws.read_net_state_file("/fake/path.json")
        assert result is None

    def test_returns_none_when_json_invalid(self):
        with patch("builtins.open", mock_open(read_data="invalid json {{")):
            result = ws.read_net_state_file("/fake/path.json")
        assert result is None

    def test_returns_none_on_oserror(self):
        with patch("builtins.open", side_effect=OSError("permission denied")):
            result = ws.read_net_state_file("/fake/path.json")
        assert result is None


class TestIsFreezeActive:
    def test_returns_true_when_fresh_frozen_flag(self):
        fresh_ts = time.time()
        state = {"owner": "texbot", "mode": "FROZEN", "ts": fresh_ts}
        assert ws.is_freeze_active(state) is True

    def test_returns_false_when_stale_frozen_flag(self):
        old_ts = time.time() - 35.0  # 35s old, past 30s TTL
        state = {"owner": "texbot", "mode": "FROZEN", "ts": old_ts}
        assert ws.is_freeze_active(state) is False

    def test_returns_false_when_state_is_none(self):
        assert ws.is_freeze_active(None) is False

    def test_returns_false_when_owner_not_texbot(self):
        state = {"owner": "other", "mode": "FROZEN", "ts": time.time()}
        assert ws.is_freeze_active(state) is False

    def test_returns_false_when_mode_not_frozen(self):
        state = {"owner": "texbot", "mode": "RUNNING", "ts": time.time()}
        assert ws.is_freeze_active(state) is False

    def test_returns_false_when_ts_missing(self):
        state = {"owner": "texbot", "mode": "FROZEN"}
        assert ws.is_freeze_active(state) is False


class TestWriteWifiState:
    def test_writes_state_with_stable_on_prefix(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            tmp_path = f.name

        try:
            ws.write_wifi_state("Redmi 9A", path=tmp_path)
            with open(tmp_path, 'r') as f:
                data = json.load(f)
            assert "wifi" in data
            assert "Redmi 9A" in data["wifi"]["state"]
            assert "stable-on:" in data["wifi"]["state"]
            assert "ts" in data["wifi"]
        finally:
            os.unlink(tmp_path)

    def test_merges_with_existing_state(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            tmp_path = f.name
            json.dump({"owner": "texbot", "mode": "FROZEN"}, f)

        try:
            ws.write_wifi_state("POCO X6 5G di Fulvio", path=tmp_path)
            with open(tmp_path, 'r') as f:
                data = json.load(f)
            assert data["owner"] == "texbot"
            assert data["mode"] == "FROZEN"
            assert "wifi" in data
            assert "POCO X6 5G di Fulvio" in data["wifi"]["state"]
        finally:
            os.unlink(tmp_path)

    def test_uses_atomic_write(self):
        with patch("builtins.open", mock_open()), \
             patch("os.makedirs"), \
             patch("os.replace") as mock_replace:
            ws.write_wifi_state("Redmi 9A", path="/fake/path.json")
        # Verify that os.replace was called (atomic write pattern)
        mock_replace.assert_called()

    def test_logs_on_oserror(self):
        with patch("builtins.open", side_effect=OSError("permission denied")), \
             patch("wifi_switch.log") as mock_log:
            ws.write_wifi_state("Redmi 9A", path="/fake/path.json")
        # Verify that error was logged
        mock_log.assert_called()
