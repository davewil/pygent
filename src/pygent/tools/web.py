"""Web tools for fetching and processing web content."""

from __future__ import annotations

import html.parser
import json
import re
from typing import Any

import httpx

from pygent.tools.base import ToolCategory, ToolRisk, tool

# Default limits
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_SIZE = 1024 * 1024  # 1MB


class WebFetchError(Exception):
    """Error during web fetch operation."""


class _HTMLToTextParser(html.parser.HTMLParser):
    """Simple HTML to text converter.

    Extracts text content from HTML, handling common elements.
    """

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._skip_content = False
        self._in_pre = False
        self._list_depth = 0
        self._skip_tags = {"script", "style", "noscript", "head", "meta", "link"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._skip_tags:
            self._skip_content = True
        elif tag == "pre":
            self._in_pre = True
        elif tag in ("ul", "ol"):
            self._list_depth += 1
            self._text_parts.append("\n")
        elif tag == "li":
            self._text_parts.append("\n- " if self._list_depth > 0 else "\n")
        elif tag in ("br", "hr"):
            self._text_parts.append("\n")
        elif tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self._text_parts.append("\n\n")
        elif tag == "a":
            # Extract href for markdown-style links
            href = dict(attrs).get("href", "")
            if href:
                self._text_parts.append("[")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._skip_tags:
            self._skip_content = False
        elif tag == "pre":
            self._in_pre = False
        elif tag in ("ul", "ol"):
            self._list_depth = max(0, self._list_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_content:
            return
        if self._in_pre:
            self._text_parts.append(data)
        else:
            # Normalize whitespace for non-preformatted text
            normalized = re.sub(r"\s+", " ", data)
            if normalized.strip():
                self._text_parts.append(normalized)

    def get_text(self) -> str:
        """Get the extracted text content."""
        text = "".join(self._text_parts)
        # Clean up excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _html_to_text(html_content: str) -> str:
    """Convert HTML content to readable text.

    Args:
        html_content: HTML string to convert.

    Returns:
        Extracted text content.
    """
    parser = _HTMLToTextParser()
    try:
        parser.feed(html_content)
        return parser.get_text()
    except Exception:
        # If parsing fails, do basic tag stripping
        text = re.sub(r"<[^>]+>", " ", html_content)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def _format_response(
    status_code: int,
    headers: dict[str, str],
    content: str,
    content_type: str,
    url: str,
    truncated: bool = False,
) -> str:
    """Format the response for output.

    Args:
        status_code: HTTP status code.
        headers: Response headers.
        content: Processed content.
        content_type: Content-Type header value.
        url: Final URL (after redirects).
        truncated: Whether content was truncated.

    Returns:
        JSON-formatted response.
    """
    result: dict[str, Any] = {
        "url": url,
        "status_code": status_code,
        "content_type": content_type,
        "content": content,
    }
    if truncated:
        result["truncated"] = True
        result["message"] = "Content was truncated due to size limit"
    return json.dumps(result, indent=2)


def _upgrade_to_https(url: str) -> str:
    """Upgrade HTTP URLs to HTTPS.

    Args:
        url: URL to upgrade.

    Returns:
        URL with HTTPS scheme.
    """
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


@tool(
    name="web_fetch",
    description="Fetch content from a URL (HTTPS enforced)",
    risk=ToolRisk.HIGH,
    category=ToolCategory.WEB,
    read_only=True,
)
async def web_fetch(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_size: int = DEFAULT_MAX_SIZE,
) -> str:
    """Fetch URL content.

    Args:
        url: URL to fetch (HTTP will be upgraded to HTTPS).
        method: HTTP method (GET, POST, etc.).
        headers: Optional request headers.
        timeout: Request timeout in seconds.
        max_size: Maximum response size in bytes.

    Returns:
        JSON response with status code, content type, and content.
        For HTML, content is converted to readable text.
        For JSON, content is pretty-printed.
        For other types, raw text is returned.

    Raises:
        WebFetchError: If the request fails.
    """
    # Validate URL
    if not url:
        raise WebFetchError("URL cannot be empty")

    # Upgrade HTTP to HTTPS
    url = _upgrade_to_https(url)

    # Validate HTTPS
    if not url.startswith("https://"):
        raise WebFetchError("Only HTTPS URLs are supported")

    # Validate method
    method = method.upper()
    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    if method not in valid_methods:
        raise WebFetchError(f"Invalid HTTP method: {method}")

    request_headers = headers or {}

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        ) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=request_headers,
            )

            # Get content type
            content_type = response.headers.get("content-type", "text/plain")

            # Check content length before reading
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_size:
                raise WebFetchError(f"Response too large: {content_length} bytes (max: {max_size})")

            # Read content with size limit
            raw_content = response.content
            truncated = False
            if len(raw_content) > max_size:
                raw_content = raw_content[:max_size]
                truncated = True

            # Decode content (try UTF-8 first, then latin-1 which always succeeds)
            try:
                text_content = raw_content.decode("utf-8")
            except UnicodeDecodeError:
                # latin-1 can decode any byte sequence (0x00-0xFF)
                text_content = raw_content.decode("latin-1")

            # Process based on content type
            if "application/json" in content_type:
                # Pretty-print JSON
                try:
                    parsed = json.loads(text_content)
                    processed_content = json.dumps(parsed, indent=2)
                except json.JSONDecodeError:
                    processed_content = text_content
            elif "text/html" in content_type:
                # Convert HTML to text
                processed_content = _html_to_text(text_content)
            else:
                # Return as-is for other content types
                processed_content = text_content

            return _format_response(
                status_code=response.status_code,
                headers=dict(response.headers),
                content=processed_content,
                content_type=content_type,
                url=str(response.url),
                truncated=truncated,
            )

    except httpx.TimeoutException as e:
        raise WebFetchError(f"Request timed out after {timeout} seconds") from e
    except httpx.ConnectError as e:
        raise WebFetchError(f"Failed to connect to {url}: {e}") from e
    except httpx.HTTPStatusError as e:
        raise WebFetchError(f"HTTP error {e.response.status_code}: {e}") from e
    except httpx.RequestError as e:
        raise WebFetchError(f"Request failed: {e}") from e
