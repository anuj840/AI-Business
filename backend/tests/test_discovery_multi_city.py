"""Tests for multi-city discovery (app/services/discovery/service.py's
_discover_across_cities) -- "several targets in one call," the same idea
as multi-industry support but across the place axis instead of category.
"""
from app.services.discovery.provider import DiscoveredBusiness, DiscoveryCriteria
from app.services.discovery.service import MAX_CITIES_PER_RUN, _discover_across_cities


class FakeProvider:
    """Records which city each call was made for and returns one canned
    result per call, so we can assert the loop actually hit each city."""

    def __init__(self, results_by_city: dict[str | None, list[DiscoveredBusiness]]):
        self.results_by_city = results_by_city
        self.calls: list[str | None] = []
        self.last_error: str | None = None

    async def discover(self, criteria: DiscoveryCriteria) -> list[DiscoveredBusiness]:
        self.calls.append(criteria.city)
        self.last_error = None
        return self.results_by_city.get(criteria.city, [])


def _business(name: str, city: str) -> DiscoveredBusiness:
    return DiscoveredBusiness(name=name, source_name="test", source_ref="x", city=city)


async def test_single_city_makes_one_call():
    provider = FakeProvider({"Houston": [_business("A", "Houston")]})
    criteria = DiscoveryCriteria(country="USA", city="Houston", industry="Roofing")

    candidates, errors = await _discover_across_cities(provider, criteria)

    assert provider.calls == ["Houston"]
    assert len(candidates) == 1
    assert errors == []


async def test_multiple_cities_makes_one_call_per_city_and_merges_results():
    provider = FakeProvider(
        {
            "Houston": [_business("A", "Houston")],
            "Austin": [_business("B", "Austin"), _business("C", "Austin")],
        }
    )
    criteria = DiscoveryCriteria(country="USA", city="Houston, Austin", industry="Roofing")

    candidates, errors = await _discover_across_cities(provider, criteria)

    assert provider.calls == ["Houston", "Austin"]
    assert len(candidates) == 3
    assert errors == []


async def test_no_city_means_one_call_with_none():
    provider = FakeProvider({None: [_business("A", "Statewide")]})
    criteria = DiscoveryCriteria(country="USA", region="Texas", industry="Roofing")

    candidates, errors = await _discover_across_cities(provider, criteria)

    assert provider.calls == [None]
    assert len(candidates) == 1


async def test_caps_at_max_cities_per_run():
    many_cities = ", ".join(f"City{i}" for i in range(MAX_CITIES_PER_RUN + 5))
    provider = FakeProvider({})
    criteria = DiscoveryCriteria(country="USA", city=many_cities, industry="Roofing")

    await _discover_across_cities(provider, criteria)

    assert len(provider.calls) == MAX_CITIES_PER_RUN


class FailingThenSucceedingProvider(FakeProvider):
    async def discover(self, criteria: DiscoveryCriteria) -> list[DiscoveredBusiness]:
        self.calls.append(criteria.city)
        if criteria.city == "BadCity":
            self.last_error = "source unavailable"
            return []
        self.last_error = None
        return self.results_by_city.get(criteria.city, [])


async def test_one_city_failing_does_not_lose_others_results():
    provider = FailingThenSucceedingProvider({"GoodCity": [_business("A", "GoodCity")]})
    criteria = DiscoveryCriteria(country="USA", city="BadCity, GoodCity", industry="Roofing")

    candidates, errors = await _discover_across_cities(provider, criteria)

    assert len(candidates) == 1
    assert candidates[0].name == "A"
    assert len(errors) == 1
    assert "BadCity" in errors[0]
