import httpx
import respx

from app.services.discovery.geocode import NOMINATIM_URL
from app.services.discovery.osm_provider import OVERPASS_URL, OpenStreetMapProvider
from app.services.discovery.provider import DiscoveryCriteria

NOMINATIM_RESPONSE = [{"boundingbox": ["29.5", "30.1", "-95.8", "-95.0"]}]

OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 123,
            "lat": 29.75,
            "lon": -95.36,
            "tags": {
                "name": "Ace Roofing",
                "craft": "roofer",
                "phone": "+1 555-0100",
                "website": "https://aceroofing.example",
                "addr:city": "Houston",
                "addr:housenumber": "100",
                "addr:street": "Main St",
            },
        },
        {
            # No name tag -- should be skipped.
            "type": "node",
            "id": 124,
            "lat": 29.76,
            "lon": -95.37,
            "tags": {"craft": "roofer"},
        },
    ]
}


@respx.mock
async def test_discover_returns_parsed_businesses():
    respx.get(NOMINATIM_URL).mock(
        return_value=httpx.Response(200, json=NOMINATIM_RESPONSE)
    )
    respx.post(OVERPASS_URL).mock(
        return_value=httpx.Response(200, json=OVERPASS_RESPONSE)
    )

    provider = OpenStreetMapProvider()
    results = await provider.discover(
        DiscoveryCriteria(country="USA", region="Texas", city="Houston", industry="Roofing", max_results=10)
    )

    assert len(results) == 1
    business = results[0]
    assert business.name == "Ace Roofing"
    assert business.website_url == "https://aceroofing.example"
    assert business.phone == "+1 555-0100"
    assert business.city == "Houston"
    assert business.source_name == "openstreetmap"
    assert business.source_ref == "node/123"
    assert business.matched_industry == "Roofer"


@respx.mock
async def test_discover_returns_empty_list_when_geocode_fails():
    respx.get(NOMINATIM_URL).mock(return_value=httpx.Response(200, json=[]))

    provider = OpenStreetMapProvider()
    results = await provider.discover(
        DiscoveryCriteria(country="Nowhereland", industry="Roofing")
    )

    assert results == []


@respx.mock
async def test_discover_returns_empty_list_when_overpass_unavailable():
    respx.get(NOMINATIM_URL).mock(
        return_value=httpx.Response(200, json=NOMINATIM_RESPONSE)
    )
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(503))

    provider = OpenStreetMapProvider()
    results = await provider.discover(
        DiscoveryCriteria(country="USA", city="Houston", industry="Roofing")
    )

    assert results == []
    # Source failure must be distinguishable from a genuine zero-results
    # match (found via manual end-to-end testing against a real 504 from
    # the public Overpass instance -- a silent [] looked identical to
    # "no businesses matched", which is misleading).
    assert provider.last_error is not None


@respx.mock
async def test_discover_supports_multiple_industries_in_one_call():
    multi_response = {
        "elements": [
            {
                "type": "node",
                "id": 200,
                "lat": 29.75,
                "lon": -95.36,
                "tags": {"name": "Ace Roofing", "craft": "roofer"},
            },
            {
                "type": "node",
                "id": 201,
                "lat": 29.76,
                "lon": -95.37,
                "tags": {"name": "Bright Dental", "amenity": "dentist"},
            },
        ]
    }
    respx.get(NOMINATIM_URL).mock(return_value=httpx.Response(200, json=NOMINATIM_RESPONSE))
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=multi_response))

    provider = OpenStreetMapProvider()
    results = await provider.discover(
        DiscoveryCriteria(country="USA", city="Houston", industry="Roofing, Dental", max_results=10)
    )

    by_name = {r.name: r for r in results}
    assert by_name["Ace Roofing"].matched_industry == "Roofer"
    assert by_name["Bright Dental"].matched_industry == "Dentist"


@respx.mock
async def test_discover_dedupes_elements_matched_by_more_than_one_clause():
    # A dentist that ALSO happens to sell dental-care products would match
    # both an amenity=dentist clause and a shop=* clause if both were in
    # the query; Overpass would return it once per matching clause.
    dup_response = {
        "elements": [
            {"type": "node", "id": 300, "tags": {"name": "Dual Match Dental", "amenity": "dentist"}},
            {"type": "node", "id": 300, "tags": {"name": "Dual Match Dental", "amenity": "dentist"}},
        ]
    }
    respx.get(NOMINATIM_URL).mock(return_value=httpx.Response(200, json=NOMINATIM_RESPONSE))
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=dup_response))

    provider = OpenStreetMapProvider()
    results = await provider.discover(
        DiscoveryCriteria(country="USA", city="Houston", industry="Dental", max_results=10)
    )

    assert len(results) == 1


@respx.mock
async def test_last_error_is_cleared_on_a_subsequent_successful_call():
    respx.get(NOMINATIM_URL).mock(
        return_value=httpx.Response(200, json=NOMINATIM_RESPONSE)
    )
    respx.post(OVERPASS_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=OVERPASS_RESPONSE)]
    )

    provider = OpenStreetMapProvider()
    criteria = DiscoveryCriteria(country="USA", city="Houston", industry="Roofing")

    await provider.discover(criteria)
    assert provider.last_error is not None

    results = await provider.discover(criteria)
    assert provider.last_error is None
    assert len(results) == 1
