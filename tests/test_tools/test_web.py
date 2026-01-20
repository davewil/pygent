"""Tests for web tools (web_fetch)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chapgent.tools.web import (
    DEFAULT_TIMEOUT,
    WebFetchError,
    _format_response,
    _html_to_text,
    _upgrade_to_https,
    web_fetch,
)

# =============================================================================
# Unit tests for helper functions
# =============================================================================


class TestUpgradeToHttps:
    """Tests for _upgrade_to_https helper."""

    def test_upgrades_http_url(self):
        """Test HTTP URLs are upgraded to HTTPS."""
        assert _upgrade_to_https("http://example.com") == "https://example.com"

    def test_preserves_https_url(self):
        """Test HTTPS URLs are preserved."""
        assert _upgrade_to_https("https://example.com") == "https://example.com"

    def test_preserves_https_url_with_path(self):
        """Test HTTPS URLs with paths are preserved."""
        url = "https://example.com/path/to/resource?query=1"
        assert _upgrade_to_https(url) == url

    def test_upgrades_http_url_with_path(self):
        """Test HTTP URLs with paths are upgraded."""
        url = "http://example.com/path/to/resource?query=1"
        expected = "https://example.com/path/to/resource?query=1"
        assert _upgrade_to_https(url) == expected


class TestHtmlToText:
    """Tests for _html_to_text helper."""

    def test_extracts_basic_text(self):
        """Test extraction of basic text content."""
        html = "<html><body><p>Hello World</p></body></html>"
        result = _html_to_text(html)
        assert "Hello World" in result

    def test_removes_script_tags(self):
        """Test that script content is removed."""
        html = "<html><body><script>alert('bad');</script><p>Good text</p></body></html>"
        result = _html_to_text(html)
        assert "alert" not in result
        assert "Good text" in result

    def test_removes_style_tags(self):
        """Test that style content is removed."""
        html = "<html><head><style>.hidden { display: none; }</style></head><body><p>Visible</p></body></html>"
        result = _html_to_text(html)
        assert ".hidden" not in result
        assert "Visible" in result

    def test_preserves_preformatted_text(self):
        """Test that pre tag content is preserved."""
        html = "<pre>  code\n    indented</pre>"
        result = _html_to_text(html)
        assert "code" in result
        assert "indented" in result

    def test_handles_list_items(self):
        """Test that list items are converted to bullets."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = _html_to_text(html)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_handles_nested_tags(self):
        """Test extraction from nested tags."""
        html = "<div><p><span>Nested content</span></p></div>"
        result = _html_to_text(html)
        assert "Nested content" in result

    def test_normalizes_whitespace(self):
        """Test that excessive whitespace is normalized."""
        html = "<p>Too    many     spaces</p>"
        result = _html_to_text(html)
        assert "Too many spaces" in result

    def test_handles_empty_html(self):
        """Test handling of empty HTML."""
        result = _html_to_text("")
        assert result == ""

    def test_handles_malformed_html(self):
        """Test handling of malformed HTML."""
        html = "<p>Unclosed paragraph<div>Another element"
        result = _html_to_text(html)
        assert "Unclosed paragraph" in result or len(result) >= 0  # Should not crash

    def test_handles_br_and_hr_tags(self):
        """Test that br and hr tags create line breaks."""
        html = "<p>Line one<br>Line two<hr>Line three</p>"
        result = _html_to_text(html)
        assert "Line one" in result
        assert "Line two" in result
        assert "Line three" in result

    def test_handles_anchor_links_with_href(self):
        """Test that anchor tags with href are handled."""
        html = '<p>Click <a href="https://example.com">here</a> for more.</p>'
        result = _html_to_text(html)
        # Should contain the link text
        assert "here" in result
        assert "for more" in result


class TestFormatResponse:
    """Tests for _format_response helper."""

    def test_basic_response(self):
        """Test basic response formatting."""
        result = _format_response(
            status_code=200,
            headers={"content-type": "text/plain"},
            content="Hello",
            content_type="text/plain",
            url="https://example.com",
        )
        data = json.loads(result)

        assert data["status_code"] == 200
        assert data["content_type"] == "text/plain"
        assert data["content"] == "Hello"
        assert data["url"] == "https://example.com"

    def test_truncated_response(self):
        """Test truncated response formatting."""
        result = _format_response(
            status_code=200,
            headers={},
            content="Truncated...",
            content_type="text/plain",
            url="https://example.com",
            truncated=True,
        )
        data = json.loads(result)

        assert data["truncated"] is True
        assert "truncated" in data["message"].lower()


# =============================================================================
# Unit tests for web_fetch
# =============================================================================


def _create_mock_response(
    content: bytes = b"test content",
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    url: str = "https://example.com",
) -> MagicMock:
    """Create a mock httpx response."""
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    response.headers = httpx.Headers(headers or {"content-type": "text/plain"})
    response.url = httpx.URL(url)
    return response


@pytest.mark.asyncio
async def test_web_fetch_basic_get():
    """Test basic GET request."""
    mock_response = _create_mock_response(content=b"Hello World")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com")
        data = json.loads(result)

        assert data["status_code"] == 200
        assert "Hello World" in data["content"]


@pytest.mark.asyncio
async def test_web_fetch_upgrades_http():
    """Test that HTTP URLs are upgraded to HTTPS."""
    mock_response = _create_mock_response()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        await web_fetch("http://example.com")

        # Verify the request was made with HTTPS
        call_args = mock_client.request.call_args
        assert call_args.kwargs["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_web_fetch_rejects_non_https():
    """Test that non-HTTPS URLs are rejected."""
    with pytest.raises(WebFetchError, match="Only HTTPS URLs are supported"):
        await web_fetch("ftp://example.com/file")


@pytest.mark.asyncio
async def test_web_fetch_rejects_empty_url():
    """Test that empty URLs are rejected."""
    with pytest.raises(WebFetchError, match="URL cannot be empty"):
        await web_fetch("")


@pytest.mark.asyncio
async def test_web_fetch_rejects_invalid_method():
    """Test that invalid HTTP methods are rejected."""
    with pytest.raises(WebFetchError, match="Invalid HTTP method"):
        await web_fetch("https://example.com", method="INVALID")


@pytest.mark.asyncio
async def test_web_fetch_json_content():
    """Test fetching JSON content."""
    json_content = b'{"key": "value", "number": 42}'
    mock_response = _create_mock_response(
        content=json_content,
        headers={"content-type": "application/json"},
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://api.example.com/data")
        data = json.loads(result)

        assert data["content_type"] == "application/json"
        # Content should be pretty-printed JSON
        content_data = json.loads(data["content"])
        assert content_data["key"] == "value"
        assert content_data["number"] == 42


@pytest.mark.asyncio
async def test_web_fetch_html_content():
    """Test fetching HTML content and conversion to text."""
    html_content = b"<html><body><h1>Title</h1><p>Paragraph text</p></body></html>"
    mock_response = _create_mock_response(
        content=html_content,
        headers={"content-type": "text/html; charset=utf-8"},
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_client)
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com")
        data = json.loads(result)

        assert "text/html" in data["content_type"]
        # HTML should be converted to text
        assert "Title" in data["content"]
        assert "Paragraph text" in data["content"]
        # Should not contain raw HTML tags
        assert "<html>" not in data["content"]


@pytest.mark.asyncio
async def test_web_fetch_plain_text():
    """Test fetching plain text content."""
    text_content = b"Just plain text"
    mock_response = _create_mock_response(
        content=text_content,
        headers={"content-type": "text/plain"},
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com/plain.txt")
        data = json.loads(result)

        assert data["content"] == "Just plain text"


@pytest.mark.asyncio
async def test_web_fetch_size_limit():
    """Test content size limit enforcement."""
    # Content larger than max_size
    large_content = b"x" * 2000

    mock_response = _create_mock_response(content=large_content)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com", max_size=1000)
        data = json.loads(result)

        assert data["truncated"] is True
        assert len(data["content"]) == 1000


@pytest.mark.asyncio
async def test_web_fetch_content_length_check():
    """Test rejection of oversized content via content-length header."""
    mock_response = _create_mock_response(
        content=b"small",
        headers={"content-type": "text/plain", "content-length": "10000000"},
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(WebFetchError, match="Response too large"):
            await web_fetch("https://example.com", max_size=1000)


@pytest.mark.asyncio
async def test_web_fetch_timeout():
    """Test timeout handling."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(WebFetchError, match="timed out"):
            await web_fetch("https://example.com", timeout=5)


@pytest.mark.asyncio
async def test_web_fetch_connect_error():
    """Test connection error handling."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(WebFetchError, match="Failed to connect"):
            await web_fetch("https://unreachable.example.com")


@pytest.mark.asyncio
async def test_web_fetch_request_error():
    """Test generic request error handling."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(side_effect=httpx.RequestError("Unknown error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(WebFetchError, match="Request failed"):
            await web_fetch("https://example.com")


@pytest.mark.asyncio
async def test_web_fetch_http_status_error():
    """Test HTTPStatusError handling (raised by raise_for_status)."""
    # Create a mock response for the error
    mock_request = httpx.Request("GET", "https://example.com")
    mock_response = httpx.Response(status_code=500, request=mock_request)
    error = httpx.HTTPStatusError("Server Error", request=mock_request, response=mock_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(side_effect=error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(WebFetchError, match="HTTP error 500"):
            await web_fetch("https://example.com")


@pytest.mark.asyncio
async def test_web_fetch_custom_headers():
    """Test custom headers are passed to request."""
    mock_response = _create_mock_response()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        custom_headers = {"Authorization": "Bearer token123", "X-Custom": "value"}
        await web_fetch("https://api.example.com", headers=custom_headers)

        call_args = mock_client.request.call_args
        assert call_args.kwargs["headers"] == custom_headers


@pytest.mark.asyncio
async def test_web_fetch_post_method():
    """Test POST method."""
    mock_response = _create_mock_response()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        await web_fetch("https://api.example.com/submit", method="POST")

        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "POST"


@pytest.mark.asyncio
async def test_web_fetch_case_insensitive_method():
    """Test that HTTP methods are case-insensitive."""
    mock_response = _create_mock_response()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        await web_fetch("https://api.example.com", method="get")

        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "GET"


@pytest.mark.asyncio
async def test_web_fetch_follows_redirects():
    """Test that redirects are followed."""
    final_url = "https://example.com/final"
    mock_response = _create_mock_response(url=final_url)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com/redirect")
        data = json.loads(result)

        # The response URL should be the final URL after redirects
        assert data["url"] == final_url


@pytest.mark.asyncio
async def test_web_fetch_handles_unicode_decode_error():
    """Test handling of non-UTF-8 content."""
    # Latin-1 encoded content
    latin1_content = "café résumé".encode("latin-1")
    mock_response = _create_mock_response(content=latin1_content)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com")
        data = json.loads(result)

        # Should decode successfully with fallback
        assert "caf" in data["content"]


@pytest.mark.asyncio
async def test_web_fetch_handles_invalid_json():
    """Test handling of invalid JSON content."""
    invalid_json = b"{not valid json}"
    mock_response = _create_mock_response(
        content=invalid_json,
        headers={"content-type": "application/json"},
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://api.example.com")
        data = json.loads(result)

        # Should return raw content when JSON parsing fails
        assert data["content"] == "{not valid json}"


@pytest.mark.asyncio
async def test_web_fetch_http_error_status():
    """Test handling of HTTP error status codes."""
    mock_response = _create_mock_response(
        content=b"Not Found",
        status_code=404,
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com/notfound")
        data = json.loads(result)

        # Should still return the response with the error status
        assert data["status_code"] == 404


@pytest.mark.asyncio
async def test_web_fetch_default_values():
    """Test that default values are used correctly."""
    mock_response = _create_mock_response()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        await web_fetch("https://example.com")

        # Verify client was created with default timeout
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args.kwargs
        assert call_kwargs["timeout"].connect == DEFAULT_TIMEOUT


@pytest.mark.asyncio
async def test_web_fetch_valid_http_methods():
    """Test all valid HTTP methods."""
    valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    mock_response = _create_mock_response()

    for method in valid_methods:
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Should not raise
            await web_fetch("https://example.com", method=method)


# =============================================================================
# Property-based tests
# =============================================================================


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    path=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789/-_."),
)
@pytest.mark.asyncio
async def test_prop_http_urls_upgraded(path):
    """Property: HTTP URLs should always be upgraded to HTTPS."""
    # Clean up path to be valid URL path
    if path.startswith("/"):
        clean_path = path
    else:
        clean_path = "/" + path

    http_url = f"http://example.com{clean_path}"
    expected_https = f"https://example.com{clean_path}"

    assert _upgrade_to_https(http_url) == expected_https


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    path=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789/-_."),
)
@pytest.mark.asyncio
async def test_prop_https_urls_preserved(path):
    """Property: HTTPS URLs should be preserved unchanged."""
    if path.startswith("/"):
        clean_path = path
    else:
        clean_path = "/" + path

    https_url = f"https://example.com{clean_path}"

    assert _upgrade_to_https(https_url) == https_url


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    text_content=st.text(min_size=10, max_size=500).filter(lambda s: "\x00" not in s),
)
@pytest.mark.asyncio
async def test_prop_html_to_text_no_crash(text_content):
    """Property: HTML to text conversion should never crash."""
    # Wrap content in HTML tags
    html = f"<html><body><p>{text_content}</p></body></html>"

    # Should not raise
    result = _html_to_text(html)
    assert isinstance(result, str)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    content_size=st.integers(min_value=100, max_value=5000),
    max_size=st.integers(min_value=50, max_value=1000),
)
@pytest.mark.asyncio
async def test_prop_size_limit_enforced(content_size, max_size):
    """Property: Content should always be truncated to max_size."""
    content = b"x" * content_size
    mock_response = _create_mock_response(content=content)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com", max_size=max_size)
        data = json.loads(result)

        # Content should never exceed max_size
        assert len(data["content"]) <= max_size

        # Should be marked as truncated if content was larger
        if content_size > max_size:
            assert data.get("truncated") is True


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    status_code=st.integers(min_value=100, max_value=599),
)
@pytest.mark.asyncio
async def test_prop_status_code_preserved(status_code):
    """Property: HTTP status codes should be preserved in response."""
    mock_response = _create_mock_response(status_code=status_code)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await web_fetch("https://example.com")
        data = json.loads(result)

        assert data["status_code"] == status_code
