"""Tests for domain age via RDAP (app/services/domain_age/rdap.py)."""
import httpx
import respx

from app.services.domain_age.rdap import (
    RDAP_BOOTSTRAP_URL,
    _extract_registrable_domain,
    get_domain_age,
)


def test_extract_registrable_domain_strips_www():
    assert _extract_registrable_domain("https://www.acmeroofing.com/contact") == "acmeroofing.com"


def test_extract_registrable_domain_without_www():
    assert _extract_registrable_domain("https://acmeroofing.com") == "acmeroofing.com"


def test_extract_registrable_domain_strips_port():
    assert _extract_registrable_domain("https://acmeroofing.com:8443/") == "acmeroofing.com"


def test_extract_registrable_domain_rejects_garbage():
    assert _extract_registrable_domain("not a url") is None


@respx.mock
async def test_get_domain_age_parses_registration_event():
    fake_rdap_response = {
        "events": [
            {"eventAction": "last changed", "eventDate": "2024-01-01T00:00:00Z"},
            {"eventAction": "registration", "eventDate": "2010-06-15T00:00:00Z"},
        ]
    }
    respx.get(RDAP_BOOTSTRAP_URL.format(domain="acmeroofing.com")).mock(
        return_value=httpx.Response(200, json=fake_rdap_response)
    )

    result = await get_domain_age("https://acmeroofing.com")

    assert result["domain"] == "acmeroofing.com"
    assert result["registered_date"] == "2010-06-15T00:00:00Z"
    assert result["age_years"] is not None
    assert result["age_years"] > 10  # registered 2010, well over a decade old by now


@respx.mock
async def test_get_domain_age_handles_404():
    respx.get(RDAP_BOOTSTRAP_URL.format(domain="acmeroofing.com")).mock(
        return_value=httpx.Response(404)
    )

    result = await get_domain_age("https://acmeroofing.com")

    assert result["age_years"] is None
    assert result["error"] is None


@respx.mock
async def test_get_domain_age_handles_service_unavailable():
    respx.get(RDAP_BOOTSTRAP_URL.format(domain="acmeroofing.com")).mock(
        return_value=httpx.Response(503)
    )

    result = await get_domain_age("https://acmeroofing.com")

    assert result["age_years"] is None
    assert result["error"] is not None


async def test_get_domain_age_returns_none_for_unparseable_url():
    result = await get_domain_age("not a url")
    assert result["domain"] is None
    assert result["age_years"] is None
