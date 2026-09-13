import pytest

from app.services.crawler.ssrf import UnsafeURLError, validate_public_url


def test_allows_public_https_url():
    assert validate_public_url("https://example.com") == "https://example.com"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "ftp://example.com",
        "http://user:pass@example.com",
    ],
)
def test_blocks_unsafe_urls(url):
    with pytest.raises(UnsafeURLError):
        validate_public_url(url)
