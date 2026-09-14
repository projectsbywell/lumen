"""HTTP client utilities for the Lumen standard library."""

import urllib.request
import urllib.error
import urllib.parse
import json
import io as _io
from typing import Optional, Dict, Any, List
from http.client import HTTPResponse


class _HTTPErrorWrapper:
    """Adapts urllib.error.HTTPError to the HTTPResponse interface."""

    def __init__(self, e: urllib.error.HTTPError):
        self.status = e.code
        self._headers = e.headers if isinstance(e.headers, dict) else dict(e.headers)
        self._body = e.read()

    def getheaders(self):
        return list(self._headers.items())

    def read(self):
        return self._body


class LumenResponse:
    """HTTP response wrapper."""

    def __init__(self, response: HTTPResponse):
        if isinstance(response, urllib.error.HTTPError):
            response = _HTTPErrorWrapper(response)
        self._response = response
        self.status_code = response.status
        self.headers = dict(response.getheaders())
        self._body = None

    @property
    def body(self) -> str:
        """Get response body as string."""
        if self._body is None:
            self._body = self._response.read().decode("utf-8")
        return self._body

    @property
    def json(self) -> Any:
        """Parse response body as JSON."""
        return json.loads(self.body)

    def text(self) -> str:
        """Get response text."""
        return self.body

    def is_success(self) -> bool:
        """Check if status is 2xx."""
        return 200 <= self.status_code < 300

    def is_redirect(self) -> bool:
        """Check if status is redirect."""
        return 300 <= self.status_code < 400

    def is_error(self) -> bool:
        """Check if status is 4xx or 5xx."""
        return self.status_code >= 400


class HTTPClient:
    """Minimal HTTP client using urllib."""

    def __init__(self, timeout: int = 30, headers: Optional[Dict[str, str]] = None):
        self.timeout = timeout
        self.headers = headers or {}

    def _build_request(self, url: str, method: str, data=None, headers: Optional[Dict[str, str]] = None) -> urllib.request.Request:
        """Build a urllib request."""
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)
        if data is not None and isinstance(data, (dict, str)):
            if isinstance(data, dict):
                data = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
        return req

    def _request(self, method: str, url: str, data=None, **kwargs) -> LumenResponse:
        """Execute HTTP request."""
        req = self._build_request(url, method, data, kwargs.get("headers"))
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return LumenResponse(resp)
        except urllib.error.HTTPError as e:
            return LumenResponse(e)
        except urllib.error.URLError:
            raise

    def get(self, url: str, **kwargs) -> LumenResponse:
        """Send GET request."""
        return self._request("GET", url, **kwargs)

    def post(self, url: str, data=None, **kwargs) -> LumenResponse:
        """Send POST request."""
        return self._request("POST", url, data=data, **kwargs)

    def put(self, url: str, data=None, **kwargs) -> LumenResponse:
        """Send PUT request."""
        return self._request("PUT", url, data=data, **kwargs)

    def delete(self, url: str, **kwargs) -> LumenResponse:
        """Send DELETE request."""
        return self._request("DELETE", url, **kwargs)

    def patch(self, url: str, data=None, **kwargs) -> LumenResponse:
        """Send PATCH request."""
        return self._request("PATCH", url, data=data, **kwargs)


# Module-level convenience functions
_client = HTTPClient()


def get(url: str, **kwargs) -> LumenResponse:
    """Send GET request with default client."""
    return _client.get(url, **kwargs)


def post(url: str, data=None, **kwargs) -> LumenResponse:
    """Send POST request with default client."""
    return _client.post(url, data=data, **kwargs)


def put(url: str, data=None, **kwargs) -> LumenResponse:
    """Send PUT request with default client."""
    return _client.put(url, data=data, **kwargs)


def delete(url: str, **kwargs) -> LumenResponse:
    """Send DELETE request with default client."""
    return _client.delete(url, **kwargs)


def request(method: str, url: str, **kwargs) -> LumenResponse:
    """Send arbitrary HTTP request."""
    return _client._request(method, url, **kwargs)
