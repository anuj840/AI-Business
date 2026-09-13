from app.services.discovery.dedup import is_duplicate, normalize_name


def test_normalize_name_strips_legal_suffixes_and_punctuation():
    assert normalize_name("ABC Roofing, LLC") == "abcroofing"
    assert normalize_name("Golden Gate Plumbing Co.") == "goldengateplumbing"


def test_is_duplicate_matches_on_normalized_name_and_city():
    existing = [("ABC Roofing LLC", "Houston", None)]
    assert is_duplicate("Abc Roofing", "Houston", None, existing) is True


def test_is_duplicate_false_when_different_city():
    existing = [("ABC Roofing LLC", "Houston", None)]
    assert is_duplicate("Abc Roofing", "Dallas", None, existing) is False


def test_is_duplicate_matches_on_exact_phone_regardless_of_name():
    existing = [("Totally Different Name", "Miami", "+15551234567")]
    assert is_duplicate("New Name Inc", None, "+15551234567", existing) is True


def test_is_duplicate_false_for_unrelated_business():
    existing = [("ABC Roofing LLC", "Houston", None)]
    assert is_duplicate("XYZ Dental", "Houston", None, existing) is False
