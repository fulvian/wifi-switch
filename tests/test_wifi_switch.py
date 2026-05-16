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
