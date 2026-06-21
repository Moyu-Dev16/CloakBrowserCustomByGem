"""Unit tests for core.browser_manager"""
import pytest
from unittest.mock import MagicMock, patch

from core.browser_manager import BrowserConfig, close_browser


class TestBrowserConfig:
    def test_default_values(self):
        config = BrowserConfig()
        assert "xiaomimimo" in config.target_url
        assert config.proxy is None
        assert config.stealth_mode is True
        assert config.timeout_minutes == 30
        assert config.sync_proxy_locale is False
        assert config.sync_proxy_timezone is False
        assert config.sync_proxy_geolocation is False
        assert config.target_email is None
        assert config.target_password is None
        assert config.email_client_id is None
        assert config.email_client_secret is None
        assert config.email_refresh_token is None
        assert config.invite_code is None
        assert config.auto_bind_create is True

    def test_custom_values(self):
        config = BrowserConfig(
            target_url="https://example.com",
            proxy="http://proxy:8080",
            stealth_mode=False,
            timeout_minutes=60,
            sync_proxy_locale=True,
            target_email="test@test.com",
            target_password="pass123",
        )
        assert config.target_url == "https://example.com"
        assert config.proxy == "http://proxy:8080"
        assert config.stealth_mode is False
        assert config.timeout_minutes == 60
        assert config.sync_proxy_locale is True
        assert config.target_email == "test@test.com"
        assert config.target_password == "pass123"


class TestCloseBrowser:
    def test_close_none_browser(self):
        logger = MagicMock()
        close_browser(None, logger)
        logger.warning.assert_called_once()

    def test_close_none_browser_no_logger(self):
        close_browser(None)

    def test_close_browser_success(self):
        browser = MagicMock()
        logger = MagicMock()
        close_browser(browser, logger)
        browser.close.assert_called_once()
        logger.success.assert_called_once()

    def test_close_browser_success_no_logger(self):
        browser = MagicMock()
        close_browser(browser)
        browser.close.assert_called_once()

    def test_close_browser_exception(self):
        browser = MagicMock()
        browser.close.side_effect = RuntimeError("close failed")
        logger = MagicMock()
        close_browser(browser, logger)
        logger.error.assert_called_once()

    def test_close_browser_exception_no_logger(self):
        browser = MagicMock()
        browser.close.side_effect = RuntimeError("close failed")
        close_browser(browser)


class TestLaunchBrowser:
    @patch("core.browser_manager.launch_browser.__module__", "core.browser_manager")
    def test_import_error_returns_none(self):
        from core.browser_manager import launch_browser
        config = BrowserConfig()
        logger = MagicMock()

        with patch.dict("sys.modules", {"cloakbrowser": None}):
            with patch("builtins.__import__", side_effect=ImportError("no cloakbrowser")):
                result = launch_browser(config, logger)
                assert result == (None, None)
