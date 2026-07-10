import pytest
from fpl_snapshot import derive_season


def test_derives_start_year_from_first_gameweek_deadline():
    bootstrap = {"events": [{"deadline_time": "2025-08-15T17:30:00Z"}]}
    assert derive_season(bootstrap) == "2025"


def test_rolls_over_when_api_flips_to_new_season():
    bootstrap = {"events": [{"deadline_time": "2026-08-14T17:30:00Z"}]}
    assert derive_season(bootstrap) == "2026"


def test_fails_loudly_rather_than_mislabelling_when_events_missing():
    with pytest.raises((KeyError, IndexError)):
        derive_season({"events": []})
