"""Unit tests for core.email_reader"""
import pytest
from unittest.mock import patch, MagicMock

from core.email_reader import strip_html, get_access_token, read_latest_verification_code


class TestStripHtml:
    def test_plain_text(self):
        assert strip_html("hello world") == "hello world"

    def test_removes_tags(self):
        assert strip_html("<b>bold</b> text") == "bold text"

    def test_removes_script_tags(self):
        result = strip_html("<script>alert('x')</script>after")
        assert "alert" not in result
        assert "after" in result

    def test_removes_style_tags(self):
        result = strip_html("<style>.x{color:red}</style>content")
        assert "color" not in result
        assert "content" in result

    def test_unescapes_html_entities(self):
        result = strip_html("&amp; &lt; &gt; &quot;")
        assert "&" in result
        assert "<" in result

    def test_collapses_whitespace(self):
        result = strip_html("<p>a</p>   <p>b</p>")
        assert "  " not in result

    def test_none_input(self):
        result = strip_html(None)
        assert result == "None" or result == ""

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_nested_tags(self):
        result = strip_html("<div><span>inner</span></div>")
        assert "inner" in result

    def test_complex_html(self):
        html = """
        <html>
        <head><style>body{margin:0}</style></head>
        <body>
            <p>Your code is <b>123456</b></p>
            <script>trackEvent()</script>
        </body>
        </html>
        """
        result = strip_html(html)
        assert "123456" in result
        assert "trackEvent" not in result
        assert "margin" not in result


class TestGetAccessToken:
    def test_raises_on_empty_client_secret(self):
        with pytest.raises(ValueError, match="Client Secret"):
            get_access_token("client_id", "", "refresh_token")

    @patch("core.email_reader.requests.post")
    def test_returns_token_on_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"access_token": "abc123"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        token = get_access_token("cid", "secret", "refresh")
        assert token == "abc123"

        call_args = mock_post.call_args
        assert "token" in call_args[0][0]
        data = call_args[1].get("data") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1]["data"]
        assert data["grant_type"] == "refresh_token"
        assert data["client_id"] == "cid"

    @patch("core.email_reader.requests.post")
    def test_raises_on_http_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.text = "error"
        mock_resp.raise_for_status.side_effect = Exception("401")
        mock_post.return_value = mock_resp

        with pytest.raises(Exception):
            get_access_token("cid", "secret", "refresh")


class TestReadLatestVerificationCode:
    def test_raises_on_missing_email(self):
        with pytest.raises(ValueError):
            read_latest_verification_code("", "cid", "secret", "refresh")

    def test_raises_on_missing_client_id(self):
        with pytest.raises(ValueError):
            read_latest_verification_code("test@test.com", "", "secret", "refresh")

    def test_raises_on_missing_refresh_token(self):
        with pytest.raises(ValueError):
            read_latest_verification_code("test@test.com", "cid", "secret", "")

    @patch("core.email_reader.get_access_token")
    def test_returns_error_on_token_failure(self, mock_token):
        mock_token.side_effect = Exception("token error")
        result = read_latest_verification_code("test@test.com", "cid", "secret", "refresh")
        assert "失败" in result or "Token" in result

    @patch("core.email_reader.requests.get")
    @patch("core.email_reader.get_access_token")
    def test_returns_no_mail_message(self, mock_token, mock_get):
        mock_token.return_value = "fake_token"

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "mailFolders" in url and "messages" not in url and "childFolders" not in url:
                resp.json.return_value = {
                    "value": [{"id": "folder1"}],
                }
            elif "childFolders" in url:
                resp.json.return_value = {"value": []}
            else:
                resp.json.return_value = {"value": []}
            return resp

        mock_get.side_effect = side_effect
        result = read_latest_verification_code("test@test.com", "cid", "secret", "refresh")
        assert "没有邮件" in result

    @patch("core.email_reader.requests.get")
    @patch("core.email_reader.get_access_token")
    def test_extracts_verification_code(self, mock_token, mock_get):
        mock_token.return_value = "fake_token"

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "mailFolders" in url and "messages" not in url and "childFolders" not in url:
                resp.json.return_value = {
                    "value": [{"id": "folder1"}],
                }
            elif "childFolders" in url:
                resp.json.return_value = {"value": []}
            elif "messages" in url:
                resp.json.return_value = {
                    "value": [{
                        "from": {"emailAddress": {"address": "noreply@notice.xiaomi.com"}},
                        "receivedDateTime": "2025-01-01T12:00:00Z",
                        "body": {"content": "<p>Your verification code is 654321</p>"},
                        "bodyPreview": "Your verification code is 654321",
                        "subject": "Verification",
                    }]
                }
            else:
                resp.json.return_value = {"value": []}
            return resp

        mock_get.side_effect = side_effect
        result = read_latest_verification_code("test@test.com", "cid", "secret", "refresh")
        assert "654321" in result
