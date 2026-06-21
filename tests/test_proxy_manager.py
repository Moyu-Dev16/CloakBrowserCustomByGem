"""Unit tests for core.proxy_manager"""
import pytest
from unittest.mock import patch, MagicMock

from core.proxy_manager import (
    parse_proxy_list,
    get_proxy,
    build_requests_proxies,
    validate_proxy,
    PROXY_MODES,
)


# ── parse_proxy_list ──────────────────────────────────────────────

class TestParseProxyList:
    def test_empty_string(self):
        assert parse_proxy_list("") == []

    def test_none_input(self):
        assert parse_proxy_list(None) == []

    def test_single_proxy(self):
        assert parse_proxy_list("http://proxy:8080") == ["http://proxy:8080"]

    def test_multiple_proxies(self):
        text = "http://p1:8080\nhttp://p2:8080\nsocks5://p3:1080"
        result = parse_proxy_list(text)
        assert result == ["http://p1:8080", "http://p2:8080", "socks5://p3:1080"]

    def test_skips_empty_lines(self):
        text = "\nhttp://p1:8080\n\n\nhttp://p2:8080\n"
        result = parse_proxy_list(text)
        assert result == ["http://p1:8080", "http://p2:8080"]

    def test_skips_comment_lines(self):
        text = "# comment\nhttp://p1:8080\n# another comment\nhttp://p2:8080"
        result = parse_proxy_list(text)
        assert result == ["http://p1:8080", "http://p2:8080"]

    def test_strips_whitespace(self):
        text = "  http://p1:8080  \n  socks5://p2:1080  "
        result = parse_proxy_list(text)
        assert result == ["http://p1:8080", "socks5://p2:1080"]

    def test_proxy_with_auth(self):
        text = "http://user:pass@host:8080"
        result = parse_proxy_list(text)
        assert result == ["http://user:pass@host:8080"]


# ── build_requests_proxies ────────────────────────────────────────

class TestBuildRequestsProxies:
    def test_empty_url(self):
        assert build_requests_proxies("") == {}
        assert build_requests_proxies(None) == {}

    def test_http_proxy(self):
        result = build_requests_proxies("http://proxy:8080")
        assert result == {"http": "http://proxy:8080", "https": "http://proxy:8080"}

    def test_https_proxy(self):
        result = build_requests_proxies("https://proxy:8443")
        assert result == {"http": "https://proxy:8443", "https": "https://proxy:8443"}

    def test_socks5_proxy(self):
        result = build_requests_proxies("socks5://proxy:1080")
        assert result == {"http": "socks5://proxy:1080", "https": "socks5://proxy:1080"}

    def test_socks5h_proxy(self):
        result = build_requests_proxies("socks5h://proxy:1080")
        assert result == {"http": "socks5h://proxy:1080", "https": "socks5h://proxy:1080"}

    def test_unknown_scheme_with_protocol(self):
        result = build_requests_proxies("ftp://proxy:21")
        assert result["http"] == "ftp://proxy:21"
        assert result["https"] == "ftp://proxy:21"

    def test_no_scheme_fallback(self):
        result = build_requests_proxies("proxy:8080")
        assert result["http"] == "http://proxy:8080"
        assert result["https"] == "http://proxy:8080"

    def test_strips_whitespace(self):
        result = build_requests_proxies("  http://proxy:8080  ")
        assert result == {"http": "http://proxy:8080", "https": "http://proxy:8080"}


# ── get_proxy ─────────────────────────────────────────────────────

class TestGetProxy:
    def test_mode_none(self):
        assert get_proxy("none") is None

    def test_mode_pool_empty_list(self):
        assert get_proxy("pool", proxy_list=[]) is None
        assert get_proxy("pool", proxy_list=None) is None

    def test_mode_pool_returns_from_list(self):
        proxies = ["http://p1:8080", "http://p2:8080"]
        result = get_proxy("pool", proxy_list=proxies)
        assert result in proxies

    def test_mode_rotating(self):
        result = get_proxy("rotating", rotating_proxy="http://rotate:8080")
        assert result == "http://rotate:8080"

    def test_mode_rotating_empty(self):
        assert get_proxy("rotating", rotating_proxy="") is None
        assert get_proxy("rotating", rotating_proxy=None) is None
        assert get_proxy("rotating", rotating_proxy="   ") is None

    def test_mode_rotating_strips(self):
        result = get_proxy("rotating", rotating_proxy="  http://r:8080  ")
        assert result == "http://r:8080"

    @patch("core.proxy_manager.requests.get")
    def test_mode_api_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "1.2.3.4:8080\n5.6.7.8:9090"
        mock_get.return_value = mock_resp

        result = get_proxy("api", api_url="http://api.example.com/proxy")
        assert result == "http://1.2.3.4:8080"

    @patch("core.proxy_manager.requests.get")
    def test_mode_api_with_scheme(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "socks5://1.2.3.4:1080"
        mock_get.return_value = mock_resp

        result = get_proxy("api", api_url="http://api.example.com/proxy")
        assert result == "socks5://1.2.3.4:1080"

    @patch("core.proxy_manager.requests.get")
    def test_mode_api_failure(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        result = get_proxy("api", api_url="http://api.example.com/proxy")
        assert result is None

    def test_mode_api_empty_url(self):
        assert get_proxy("api", api_url="") is None
        assert get_proxy("api", api_url=None) is None

    def test_unknown_mode(self):
        assert get_proxy("unknown_mode") is None


# ── validate_proxy ────────────────────────────────────────────────

class TestValidateProxy:
    def test_empty_proxy(self):
        ok, msg = validate_proxy("")
        assert ok is False
        assert "空" in msg

    def test_none_proxy(self):
        ok, msg = validate_proxy(None)
        assert ok is False

    @patch("core.proxy_manager.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"origin": "1.2.3.4"}
        mock_get.return_value = mock_resp

        ok, msg = validate_proxy("http://proxy:8080")
        assert ok is True
        assert "1.2.3.4" in msg

    @patch("core.proxy_manager.requests.get")
    def test_success_json_parse_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("bad json")
        mock_get.return_value = mock_resp

        ok, msg = validate_proxy("http://proxy:8080")
        assert ok is True

    @patch("core.proxy_manager.requests.get")
    def test_bad_status_code(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        ok, msg = validate_proxy("http://proxy:8080")
        assert ok is False
        assert "403" in msg

    @patch("core.proxy_manager.requests.get")
    def test_proxy_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ProxyError("refused")

        ok, msg = validate_proxy("http://proxy:8080")
        assert ok is False
        assert "连接失败" in msg

    @patch("core.proxy_manager.requests.get")
    def test_connect_timeout(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectTimeout()

        ok, msg = validate_proxy("http://proxy:8080", timeout=5)
        assert ok is False
        assert "超时" in msg

    @patch("core.proxy_manager.requests.get")
    def test_read_timeout(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ReadTimeout()

        ok, msg = validate_proxy("http://proxy:8080")
        assert ok is False
        assert "超时" in msg

    @patch("core.proxy_manager.requests.get")
    def test_import_error_socks(self, mock_get):
        mock_get.side_effect = ImportError("pysocks")

        ok, msg = validate_proxy("socks5://proxy:1080")
        assert ok is False
        assert "PySocks" in msg


# ── PROXY_MODES constant ─────────────────────────────────────────

class TestProxyModes:
    def test_has_expected_keys(self):
        assert "none" in PROXY_MODES
        assert "pool" in PROXY_MODES
        assert "rotating" in PROXY_MODES
        assert "api" in PROXY_MODES
