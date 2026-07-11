"""Shared page helpers: the chart palette and official FPL asset URLs."""

import pandas as pd
import streamlit as st

# Hues from the validated reference palette (dataviz skill): blue primary,
# aqua secondary, each with a dark-surface step; muted ink for reference lines.
LIGHT, DARK = ("#2a78d6", "#1baf7a"), ("#3987e5", "#199e70")
MUTED_INK = "#898781"

# Official Premier League asset CDN, keyed on the stable global asset codes
# (stg_fpl_teams.team_code / stg_fpl_players.player_code). Hotlinked from the
# same URLs the FPL site itself serves -- nothing is stored in this repo.
_BADGE_URL = "https://resources.premierleague.com/premierleague/badges/70/t{code}.png"
_PHOTO_URL = "https://resources.premierleague.com/premierleague/photos/players/{size}/p{code}.png"


def series_hues() -> tuple[str, str]:
    """(blue, aqua) pair for the viewer's theme; light is the safe fallback."""
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except AttributeError:
        return LIGHT


def text_ink() -> str:
    """Chart label ink matching Streamlit's own body-text color per theme."""
    try:
        return "#fafafa" if st.context.theme.type == "dark" else "#31333f"
    except AttributeError:
        return "#31333f"


def text_halo() -> str:
    """Chart label halo matching the surface, so labels stay readable over marks."""
    try:
        return "#0e1117" if st.context.theme.type == "dark" else "#ffffff"
    except AttributeError:
        return "#ffffff"


def badge_url(team_code) -> str | None:
    return None if pd.isna(team_code) else _BADGE_URL.format(code=int(team_code))


def photo_url(player_code, size: str = "110x140") -> str | None:
    if pd.isna(player_code):
        return None
    return _PHOTO_URL.format(size=size, code=int(player_code))
