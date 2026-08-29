"""Small shared HTTP and HTML helpers for local CLI tools."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_BYTES = 2_000_000


class WebFetchError(RuntimeError):
    """Raised when a remote page cannot be retrieved as bounded text."""


class _VisibleTextParser(HTMLParser):
    """Collect page-body text while excluding non-content and site-chrome elements."""

    # These semantic landmarks normally contain repeated site chrome.  Keeping
    # them in an embedding corpus produces attractive but unhelpful matches
    # such as navigation vocabulary or a footer's list of links.
    _IGNORED_TAGS = {
        "script", "style", "noscript", "template", "svg",
        "header", "nav", "footer", "aside", "form",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in self._IGNORED_TAGS:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data)


def fetch_url_text(
    url: str,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    user_agent: str = "cli_tool.py",
) -> str:
    """Fetch one HTTP(S) URL with a timeout and a bounded response size."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WebFetchError("URL must use http or https and include a host.")
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(max_bytes + 1)
    except (OSError, URLError) as error:
        raise WebFetchError(str(error)) from error
    if len(body) > max_bytes:
        raise WebFetchError(f"response exceeds the {max_bytes:,}-byte limit")
    return body.decode(charset, errors="replace")


def html_to_text(document: str) -> str:
    """Return whitespace-normalized visible text from an HTML response."""

    parser = _VisibleTextParser()
    try:
        parser.feed(document)
        parser.close()
    except Exception as error:  # HTMLParser failures are malformed input errors
        raise WebFetchError(f"cannot parse HTML: {error}") from error
    text = "\n".join(part.strip() for part in parser.parts if part.strip())
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
