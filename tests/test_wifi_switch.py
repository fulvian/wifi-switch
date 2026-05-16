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
