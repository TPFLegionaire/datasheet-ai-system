#!/usr/bin/env python3
"""
ProLabs Branding Module for Datasheet AI Comparison System

This module provides ProLabs branding elements and styling for the Streamlit application:
1. Color scheme matching ProLabs website
2. Custom CSS for styling Streamlit components
3. Helper functions for adding ProLabs branding elements
4. Logo and header components
5. Theme configuration
"""

import streamlit as st
import base64
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import os

# -----------------------------------------------------------------------------
# ProLabs Color Scheme
# -----------------------------------------------------------------------------

# Primary colors
PROLABS_NAVY = "#002554"       # Primary dark blue
PROLABS_TEAL = "#0F8B8D"       # Accent teal
PROLABS_LIGHT_BLUE = "#4A90E2"  # Light blue accent
PROLABS_GRAY = "#58595B"       # Text and details gray

# Secondary colors
PROLABS_WHITE = "#FFFFFF"      # Background white
PROLABS_LIGHT_GRAY = "#F5F7FA" # Light gray background
PROLABS_MEDIUM_GRAY = "#D8D8D8" # Medium gray for borders
PROLABS_BLACK = "#000000"      # Deep black for text

# Functional colors
PROLABS_SUCCESS = "#00A878"    # Success green
PROLABS_WARNING = "#FFC857"    # Warning yellow
PROLABS_ERROR = "#E63946"      # Error red
PROLABS_INFO = "#4A90E2"       # Info blue

# Footer color
PROLABS_FOOTER_BG = "#E9EEF4"

# -----------------------------------------------------------------------------
# Logo and Assets
# -----------------------------------------------------------------------------

i# IMPORTANT:
# Replace `PROLABS_LOGO_BASE64` with the actual encoded PNG/SVG for production.
# For now we keep a tiny 1×1 PNG (transparent) as a placeholder to avoid
# multi-MB blobs in the repo while still allowing <img> to be rendered.
_TRANSPARENT_PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8A"
    "AAwMBlC1nKgAAAAASUVORK5CYII="
)
PROLABS_LOGO_BASE64 = _TRANSPARENT_PX

# -----------------------------------------------------------------------------
# Streamlit CSS helpers
# -----------------------------------------------------------------------------

def _build_css() -> str:
    """Return a CSS string that applies ProLabs styling to Streamlit."""
    return f"""
/* -------- ProLabs Global -------- */
html, body {{
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}}
.main {{
    background: {PROLABS_WHITE};
}}

/* Header bar */
.prolabs-header {{
    background: {PROLABS_NAVY};
    color: {PROLABS_WHITE};
    padding: 0.8rem 1rem;
    display: flex;
    align-items: center;
}}
.prolabs-header img {{
    height: 32px;
    margin-right: 0.8rem;
}}
.prolabs-header h1 {{
    font-size: 1.35rem;
    margin: 0;
}}

/* Footer */
.prolabs-footer {{
    background: {PROLABS_FOOTER_BG};
    color: {PROLABS_GRAY};
    font-size: 0.8rem;
    text-align: center;
    padding: 0.7rem;
    margin-top: 2rem;
}}

/* Cards */
.prolabs-card {{
    background: {PROLABS_WHITE};
    border: 1px solid {PROLABS_MEDIUM_GRAY};
    border-radius: 8px;
    padding: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
    margin-bottom: 1rem;
}}

/* Buttons */
.stButton>button {{
    background-color: {PROLABS_TEAL};
    color: {PROLABS_WHITE};
    border: 0;
}}
.stButton>button:hover {{
    background-color: {PROLABS_LIGHT_BLUE};
    color: {PROLABS_WHITE};
}}
"""


def inject_prolabs_css() -> None:
    """Inject CSS styling into the current Streamlit app."""
    st.markdown(f"<style>{_build_css()}</style>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# UI helper components
# -----------------------------------------------------------------------------

def render_header(title: str = "Datasheet AI Comparison System",
                  show_logo: bool = True) -> None:
    """Render a top header bar with ProLabs styling."""
    inject_prolabs_css()  # ensure CSS only once (idempotent)
    logo_html = ""
    if show_logo:
        logo_html = (
            f'<img src="data:image/png;base64,{PROLABS_LOGO_BASE64}" '
            f'alt="ProLabs logo" />'
        )
    st.markdown(
        f"""
        <div class="prolabs-header">
            {logo_html}
            <h1>{title}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer(text: str = "© 2024 ProLabs. All rights reserved.") -> None:
    """Render a footer bar at the bottom of the page."""
    inject_prolabs_css()
    st.markdown(f'<div class="prolabs-footer">{text}</div>',
                unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Streamlit theme dictionary (optional, can be added to .streamlit/config.toml)
# -----------------------------------------------------------------------------

STREAMLIT_THEME: dict = {
    "primaryColor": PROLABS_TEAL,
    "backgroundColor": PROLABS_WHITE,
    "secondaryBackgroundColor": PROLABS_LIGHT_GRAY,
    "textColor": PROLABS_NAVY,
    "font": "sans serif",
}
iVBORw0KGgoAAAANSUhEUgAAAMgAAADICAYAAACtWK6eAAAACXBIWXMAAAsTAAALEwEAmpwYAAAF
EmlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0w
TXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRh
LyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDUgNzkuMTYzNDk5LCAyMDE4LzA4LzEz
LTE2OjQwOjIyICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3Jn
LzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0i
IiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOmRjPSJodHRw
Oi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIgeG1sbnM6cGhvdG9zaG9wPSJodHRwOi8vbnMu
YWRvYmUuY29tL3Bob3Rvc2hvcC8xLjAvIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNv
bS94YXAvMS4wL21tLyIgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9z
VHlwZS9SZXNvdXJjZUV2ZW50IyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ0Mg
MjAxOSAoV2luZG93cykiIHhtcDpDcmVhdGVEYXRlPSIyMDIzLTA2LTE0VDEwOjIxOjEwKzAyOjAw
IiB4bXA6TW9kaWZ5RGF0ZT0iMjAyMy0wNi0xNFQxMDoyMjoxMCswMjowMCIgeG1wOk1ldGFkYXRh
RGF0ZT0iMjAyMy0wNi0xNFQxMDoyMjoxMCswMjowMCIgZGM6Zm9ybWF0PSJpbWFnZS9wbmciIHBo
b3Rvc2hvcDpDb2xvck1vZGU9IjMiIHBob3Rvc2hvcDpJQ0NQcm9maWxlPSJzUkdCIElFQzYxOTY2
LTIuMSIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDowMWE5ZTBmMC1jMzA1LTI0NGMtOTZkYS1k
ZTUyZjg3YTc3OTMiIHhtcE1NOkRvY3VtZW50SUQ9InhtcC5kaWQ6MDFhOWUwZjAtYzMwNS0yNDRj
LTk2ZGEtZGU1MmY4N2E3NzkzIiB4bXBNTTpPcmlnaW5hbERvY3VtZW50SUQ9InhtcC5kaWQ6MDFh
OWUwZjAtYzMwNS0yNDRjLTk2ZGEtZGU1MmY4N2E3NzkzIj4gPHhtcE1NOkhpc3Rvcnk+IDxyZGY6
U2VxPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0iY3JlYXRlZCIgc3RFdnQ6aW5zdGFuY2VJRD0ieG1w
LmlpZDowMWE5ZTBmMC1jMzA1LTI0NGMtOTZkYS1kZTUyZjg3YTc3OTMiIHN0RXZ0OndoZW49IjIw
MjMtMDYtMTRUMTA6MjE6MTArMDI6MDAiIHN0RXZ0OnNvZnR3YXJlQWdlbnQ9IkFkb2JlIFBob3Rv
c2hvcCBDQyAyMDE5IChXaW5kb3dzKSIvPiA8L3JkZjpTZXE+IDwveG1wTU06SGlzdG9yeT4gPC9y
ZGY6RGVzY3JpcHRpb24+IDwvcmRmOlJERj4gPC94OnhtcG1ldGE+IDw/eHBhY2tldCBlbmQ9InIi
Pz7VSBZ/AAAWYElEQVR4nO3deXRUVZ7G8e9NVUIgYQmLLELYZJNFQGQTEFFaFgWURRqXdttWu1Xc
urvV7tFu7VZbbesWFWlxaxVRcUHZBUQQZN8JO0nYAgQSQpZK3T9uEkNIpVKpqrfcqvf5nJMDVLj3
vVX13Lrv3Hvfq4wxKKVCi3E7gFLeTAuklI22QEq5SQuklI22QErZaAuklI22QErZaAuklI22QErZ
aAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuk
lI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22
QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZ
aAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuk
lI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZaAuklI22QErZJLgdQHmX
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
ROYPAfwsYOSZ2Yi7R+aPGkCBzOxLku6TNHPUPxPoIjJ/GuDPAkaemY24e2T+rAEUyMy+LOl+STNG
/TOBLiLz5wH+LGDkmdmIu0fmLxpAgczsK5IekDR91D8T6CIyfw3wZwEjz8xG3D0yf9MACmRmX5X0
oKRpo/6ZQBeR+fsAfxYw8sxsxN0j83cNoEBm9jVJD0maOuqfCXQRmX8M8GcBI8/MRtw9Mv/UAAr0
f2b2dUkPS5oy6p8JdBGZfwX4s4CRZ2Yj7h6Zf2sABTKzb0h6RNLkUf9MoIvI/GeAPwsYeWY24u6R
+Y8GUCAz+6akh/X/Ak0a9c8EOojMfwf4s4CRZ2Yj7h6Z/2kABTKzb0l6VNJBo/6ZQBeR+d8AfxYw
8sxsxN0j8z8NoEBm9m1Jj0maOOqfCXQRmf8N8GcBI8/MRtw9Mv/XAApkZt+R9LikCaP+mUAXkfl/
gD8LGHlmNuLukdnUAApkZt+V9ISkA0b9M4EuIrM5wJ8FjDwzG3H3yGxpAAUys+9JelLSAaP+mUAX
kdka4M8CRp6Zjbh7ZLY1gAKZ2fclPSVp/Kh/JtBFZLYH+LOAkWdmI+4emR0NoEBmdoWkpyWNG/XP
BLqIzI4B/ixg5JnZiLtHZlcDKJCZ/UDSH0f9M4EeRGZ3gD8LGHlmNuLukdnTAApkZj+U9Meof6aZ
HWRmHzazq8zsJjN7zMw2m9lOM2ua2T4za5jZDjPbZmabzGyDma0zs7Vm9qKZPW9mz5rZM2b2lJk9
YWaPmdmjZvaImT1kZg+a2f1mdq+Z3W1md5nZnWZ2u5ndZma3mNnNZnajmd1gZteb2XVmdq2ZXWNm
V5vZVWZ2pZldYWaXm9llZnapmV1iZheb2UVmttzMlpnZUjNbYmaLzWyRmS00swVmNt/M5pnZXDOb
Y2azzWyWmc00sxlmNt3MppnZVDObYmaTzWySmU00swlmNt7MxpnZWDMbY2ajZjZqZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZi
ZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYj
ZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2
YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJm
I2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm
NmJmI2Y2YmYjZjZiZiNmNmJmI2Y2YmYjZjZiZiNm