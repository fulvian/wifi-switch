import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock
import pytest
import wifi_switch as ws


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
             patch("time.sleep", side_effect=[StopIteration()]):
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
