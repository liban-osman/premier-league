"""Shared page helpers: the chart palette and official FPL asset URLs."""

import pandas as pd
import streamlit as st

# Hues from the validated reference palette (dataviz skill): blue primary,
# aqua secondary, each with a dark-surface step; muted ink for reference lines.
LIGHT, DARK = ("#2a78d6", "#1baf7a"), ("#3987e5", "#199e70")
MUTED_INK = "#898781"

# Status colors (fixed status palette from the dataviz skill -- never reused
# for a series/category, so a color never impersonates "good/bad" by accident).
# "hold" isn't good or bad, so it borrows the neutral categorical blue rather
# than one of the four true status steps.
STATUS_COLORS = {
    "transfer_in": "#0ca30c",  # good
    "hold": "#3987e5",  # neutral
    "monitor": "#fab219",  # warning
    "drop": "#d03b3b",  # critical
}

# Position hues: four categorical slots not already spoken for by status
# (blue/green/yellow/red above), in the palette's fixed order.
POSITION_COLORS = {
    "GKP": "#9085e9",  # violet -- also the brand accent; goalkeepers already
    "DEF": "#199e70",  # aqua      wear a visually distinct kit in real football,
    "MID": "#d95926",  # orange    so reusing the site's own accent hue for GKP
    "FWD": "#d55181",  # magenta   reads as intentional, not a collision.
}

# Home page's four "today's highlights" cards -- one per destination page,
# not a status/position, so its own small fixed list keyed by position index.
HIGHLIGHT_COLORS = ["#00ff85", "#04f5ff", "#ff2882", "#ebff00"]

# Global look: broadcast-style display font, gradient hero, lifted cards.
# Colors mirror .streamlit/config.toml; this only adds what [theme] can't.
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');
html, body, .stApp, [class*="st-"], button, input { font-family: 'Inter', system-ui, sans-serif; }
h1, h2, h3 { font-family: 'Inter', system-ui, sans-serif !important; font-weight: 700;
    letter-spacing: -0.02em; }
.hero h1, .big-stat { font-family: 'Barlow Condensed', sans-serif !important;
    letter-spacing: 0.01em; text-transform: uppercase; }
.hero { background: linear-gradient(115deg, #38003c 0%, #6a0f7a 55%, #00b86b 130%);
    border-radius: 20px; padding: 2.4rem 2.6rem; margin-bottom: 1.5rem;
    border: 1px solid rgba(255,255,255,0.14); }
.hero h1 { font-size: 3.4rem; line-height: 1; margin: 0 0 0.6rem 0; padding: 0; color: #fff; }
.hero p { font-size: 1.1rem; max-width: 52rem; margin: 0; color: rgba(255,255,255,0.88); }
.hero-kicker { color: #00ff85; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; font-size: 0.8rem; margin-bottom: 0.5rem; }
.kicker { color: rgba(255,255,255,0.65); font-size: 0.75rem; font-weight: 700;
    letter-spacing: 0.14em; text-transform: uppercase; }
.big-stat { font-size: 2.6rem; font-weight: 800; line-height: 1.05; margin: 0.15rem 0; }
[class*="st-key-highlight-"], [class*="st-key-nav-"] {
    background: linear-gradient(160deg, #2f0a39 0%, #1d0524 100%) !important;
    border-radius: 16px !important; transition: transform .15s ease, box-shadow .15s ease; }
[class*="st-key-status-"] { border-radius: 14px !important; padding: 0.35rem 0.2rem;
    border-color: rgba(255,255,255,0.22) !important; box-shadow: 0 2px 10px rgba(0,0,0,0.35);
    transition: transform .15s ease, box-shadow .15s ease; }
[class*="st-key-status-"]:hover { transform: translateY(-2px);
    box-shadow: 0 8px 22px rgba(0,0,0,0.4); }
[class*="st-key-status-"] [data-testid="stColumn"]:first-child img { border-radius: 12px;
    background: radial-gradient(circle at 50% 30%,
    rgba(255,255,255,0.35), rgba(255,255,255,0.08)); }
[class*="st-key-status-"] * { color: #ffffff !important; }
[class*="st-key-status-"] [data-testid="stCaptionContainer"] *
    { color: rgba(255,255,255,0.82) !important; }
[class*="st-key-status-"] p { font-size: 1rem; }
[class*="st-key-highlight-"]:hover, [class*="st-key-nav-"]:hover {
    transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.45); }
"""


def inject_theme_css() -> None:
    """Colored left-border card accents keyed off each container's `key`.
    Streamlit's [theme] reaches page chrome (buttons, inputs, dataframes) but
    has no concept of *this specific player's status* -- that has to be a
    CSS rule per entity, layered on top. Call once per app run (from
    streamlit_app.py, before pg.run()); every page reruns that file's full
    body on every interaction, so one call covers all pages."""
    rules = [
        f'[class*="st-key-status-{status}-"] {{ border-left: 4px solid {color} !important; '
        f"background: linear-gradient(135deg, {color}40 0%, #6d2d90 38%, #4f1a6e 100%) "
        f"!important; }}"
        for status, color in STATUS_COLORS.items()
    ] + [
        f'[class*="st-key-highlight-{i}"] {{ border-top: 3px solid {color} !important; }}'
        for i, color in enumerate(HIGHLIGHT_COLORS)
    ]
    st.markdown(f"<style>{BASE_CSS}{''.join(rules)}</style>", unsafe_allow_html=True)


def hero(title: str, subtitle: str, kicker: str = "") -> None:
    """Gradient banner for a page's top. Plain HTML so it can be reused by
    every page without per-page CSS."""
    kicker_html = f'<div class="hero-kicker">{kicker}</div>' if kicker else ""
    st.markdown(
        f'<div class="hero">{kicker_html}<h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def position_badge(position: str | None) -> str:
    """Small colored HTML span for a position code, for use inside st.markdown
    with unsafe_allow_html=True. Empty string if position is missing.
    Text uses theme ink rather than the raw hue: these hues are dark-surface
    steps (>=3:1 on the dark background only), so the identity color carries
    via the background wash + border and the label stays legible even if a
    viewer switches to Streamlit's built-in Light theme."""
    if not position or pd.isna(position):
        return ""
    color = POSITION_COLORS.get(position, MUTED_INK)
    return (
        f'<span style="background:{color}25; color:{text_ink()}; border:1px solid {color}66; '
        f"border-radius:4px; padding:1px 6px; font-size:0.75em; font-weight:600; "
        f'margin-left:6px;">{position}</span>'
    )


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
