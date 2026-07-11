import pytest
from understat_snapshot import parse_season_start_year, split_league_payload


def test_parses_season_start_year_from_league_page_title():
    html = "<title>EPL xG Table and Scorers for the 2025/2026 season | Understat.com</title>"
    assert parse_season_start_year(html) == "2025"


def test_fails_loudly_when_title_format_changes():
    with pytest.raises(ValueError):
        parse_season_start_year("<title>Some redesigned page | Understat.com</title>")


def test_splits_payload_into_three_top_level_arrays():
    payload = {
        "players": [{"id": "1"}],
        "dates": [{"id": "10"}, {"id": "11"}],
        "teams": {"83": {"id": "83", "title": "Arsenal"}, "87": {"id": "87", "title": "Spurs"}},
    }
    files = split_league_payload(payload)
    assert set(files) == {"players.json", "matches.json", "teams.json"}
    # the teams dict flattens to a plain list; everything lands as an array
    assert all(isinstance(rows, list) for rows in files.values())
    assert {t["title"] for t in files["teams.json"]} == {"Arsenal", "Spurs"}


def test_fails_loudly_when_payload_shape_changes():
    with pytest.raises(KeyError):
        split_league_payload({"players": [], "teams": {}})  # no 'dates' block
