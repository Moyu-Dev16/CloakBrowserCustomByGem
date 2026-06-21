"""Unit tests for core.config_store"""
import os
import tempfile
import pytest
from unittest.mock import patch

from core.config_store import load_config, save_config, CONFIG_FILE


class TestLoadConfig:
    def test_default_values_when_no_file(self):
        with patch("core.config_store.CONFIG_FILE", "/tmp/nonexistent_config_12345.ini"):
            config = load_config()
            assert config["stealth_mode"] is True
            assert config["proxy_mode"] == "无代理"
            assert config["proxy_pool"] == ""
            assert config["rotating_proxy"] == ""
            assert config["proxy_api_url"] == ""
            assert config["timeout_minutes"] == 30
            assert config["email_pool"] == ""
            assert config["sync_proxy_locale"] is False
            assert config["sync_proxy_timezone"] is False
            assert config["sync_proxy_geolocation"] is False
            assert config["auto_bind_create"] is True
            assert config["email_client_secret"] == ""

    def test_loads_from_ini_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[Settings]\n")
            f.write("stealth_mode = False\n")
            f.write("proxy_mode = 代理池\n")
            f.write("proxy_pool = http://p1:8080|#|http://p2:8080\n")
            f.write("rotating_proxy = http://rotate:9090\n")
            f.write("proxy_api_url = http://api.test.com\n")
            f.write("target_url = https://example.com\n")
            f.write("timeout_minutes = 60\n")
            f.write("email_pool = a@test.com|#|b@test.com\n")
            f.write("sync_proxy_locale = True\n")
            f.write("sync_proxy_timezone = True\n")
            f.write("sync_proxy_geolocation = True\n")
            f.write("auto_bind_create = False\n")
            f.write("email_client_secret = secret123\n")
            tmp_path = f.name

        try:
            with patch("core.config_store.CONFIG_FILE", tmp_path):
                config = load_config()
                assert config["stealth_mode"] is False
                assert config["proxy_mode"] == "代理池"
                assert "http://p1:8080" in config["proxy_pool"]
                assert "http://p2:8080" in config["proxy_pool"]
                assert config["rotating_proxy"] == "http://rotate:9090"
                assert config["proxy_api_url"] == "http://api.test.com"
                assert config["target_url"] == "https://example.com"
                assert config["timeout_minutes"] == 60
                assert "a@test.com" in config["email_pool"]
                assert config["sync_proxy_locale"] is True
                assert config["sync_proxy_timezone"] is True
                assert config["sync_proxy_geolocation"] is True
                assert config["auto_bind_create"] is False
                assert config["email_client_secret"] == "secret123"
        finally:
            os.unlink(tmp_path)

    def test_partial_config_uses_fallbacks(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[Settings]\n")
            f.write("stealth_mode = True\n")
            tmp_path = f.name

        try:
            with patch("core.config_store.CONFIG_FILE", tmp_path):
                config = load_config()
                assert config["stealth_mode"] is True
                assert config["proxy_mode"] == "无代理"
                assert config["timeout_minutes"] == 30
        finally:
            os.unlink(tmp_path)


class TestSaveConfig:
    def test_saves_and_reloads(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            tmp_path = f.name

        try:
            settings = {
                "stealth_mode": False,
                "proxy_mode": "代理池",
                "proxy_pool": "http://p1:8080\nhttp://p2:8080",
                "rotating_proxy": "http://rotate:9090",
                "proxy_api_url": "http://api.test.com",
                "target_url": "https://example.com",
                "timeout_minutes": 45,
                "email_pool": "a@test.com\nb@test.com",
                "sync_proxy_locale": True,
                "sync_proxy_timezone": True,
                "sync_proxy_geolocation": True,
                "auto_bind_create": False,
                "email_client_secret": "mysecret",
            }

            with patch("core.config_store.CONFIG_FILE", tmp_path):
                save_config(settings)

                loaded = load_config()
                assert loaded["stealth_mode"] is False
                assert loaded["proxy_mode"] == "代理池"
                assert "http://p1:8080" in loaded["proxy_pool"]
                assert "http://p2:8080" in loaded["proxy_pool"]
                assert loaded["rotating_proxy"] == "http://rotate:9090"
                assert loaded["timeout_minutes"] == 45
                assert loaded["sync_proxy_locale"] is True
                assert loaded["auto_bind_create"] is False
                assert loaded["email_client_secret"] == "mysecret"
        finally:
            os.unlink(tmp_path)

    def test_saves_defaults_for_missing_keys(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            tmp_path = f.name

        try:
            with patch("core.config_store.CONFIG_FILE", tmp_path):
                save_config({})

                loaded = load_config()
                assert loaded["stealth_mode"] is True
                assert loaded["proxy_mode"] == "无代理"
                assert loaded["timeout_minutes"] == 30
        finally:
            os.unlink(tmp_path)

    def test_newlines_in_proxy_pool_roundtrip(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            tmp_path = f.name

        try:
            settings = {
                "proxy_pool": "http://a:1\nhttp://b:2\nhttp://c:3",
                "email_pool": "x@test.com\ny@test.com",
            }

            with patch("core.config_store.CONFIG_FILE", tmp_path):
                save_config(settings)
                loaded = load_config()
                lines = loaded["proxy_pool"].strip().splitlines()
                assert len(lines) == 3
                assert lines[0] == "http://a:1"
                assert lines[2] == "http://c:3"
        finally:
            os.unlink(tmp_path)
