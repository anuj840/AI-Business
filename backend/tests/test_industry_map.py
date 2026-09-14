from app.services.discovery.industry_map import label_from_osm_tags, resolve_tags, split_industries


def test_resolves_known_industry():
    assert resolve_tags("Roofing") == [("craft", "roofer")]
    assert resolve_tags("roofing companies") == [("craft", "roofer")]


def test_resolves_case_insensitively():
    assert resolve_tags("DENTAL") == [("amenity", "dentist")]


def test_returns_none_for_unknown_industry():
    assert resolve_tags("underwater basket weaving") is None


def test_split_industries_handles_multiple_comma_separated_terms():
    assert split_industries("Roofing, Plumbing,  HVAC") == ["Roofing", "Plumbing", "HVAC"]


def test_split_industries_handles_single_term():
    assert split_industries("Roofing") == ["Roofing"]


def test_split_industries_ignores_empty_segments():
    assert split_industries("Roofing, , Plumbing") == ["Roofing", "Plumbing"]


def test_label_from_osm_tags_prefers_craft_then_amenity_then_shop():
    assert label_from_osm_tags({"craft": "roofer"}) == "Roofer"
    assert label_from_osm_tags({"amenity": "dentist"}) == "Dentist"
    assert label_from_osm_tags({"shop": "car_repair"}) == "Car Repair"


def test_label_from_osm_tags_returns_none_when_no_relevant_key():
    assert label_from_osm_tags({"landuse": "residential"}) is None
