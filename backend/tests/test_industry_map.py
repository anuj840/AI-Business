from app.services.discovery.industry_map import resolve_tags


def test_resolves_known_industry():
    assert resolve_tags("Roofing") == [("craft", "roofer")]
    assert resolve_tags("roofing companies") == [("craft", "roofer")]


def test_resolves_case_insensitively():
    assert resolve_tags("DENTAL") == [("amenity", "dentist")]


def test_returns_none_for_unknown_industry():
    assert resolve_tags("underwater basket weaving") is None
