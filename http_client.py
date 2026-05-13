import requests


DEFAULT_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_session = requests.Session()
_session.headers.update(DEFAULT_BROWSER_HEADERS)


def http_get(url, **kwargs):
    headers = DEFAULT_BROWSER_HEADERS.copy()
    headers.update(kwargs.pop("headers", {}) or {})
    return _session.get(url, headers=headers, **kwargs)
