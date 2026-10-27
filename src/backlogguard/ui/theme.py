"""Identidad visual de CFOTech sobre Streamlit: franja superior, títulos en índigo y pestañas con subrayado verde.

Los colores base los fija `.streamlit/config.toml`; acá va solo lo que el tema de Streamlit no alcanza a expresar.
"""
from __future__ import annotations

import streamlit as st

INDIGO = "#13056D"
GREEN = "#59AE01"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@600;700&family=Source+Sans+3:wght@400;600;700&display=swap');
html, body, [class*="st-"], .stApp {{ font-family: 'Source Sans 3', 'Segoe UI', sans-serif; }}
h1, h2, h3, h4 {{ font-family: 'Outfit', 'Segoe UI', sans-serif; color: {INDIGO}; }}
.bg-top {{ background: {INDIGO}; border-bottom: 5px solid {GREEN}; border-radius: 8px; padding: 14px 20px; margin-bottom: 8px;
          display: flex; flex-wrap: wrap; align-items: center; gap: 8px 24px; color: #fff; }}
.bg-top .brand {{ font-family: 'Outfit', sans-serif; font-weight: 700; font-size: 22px; letter-spacing: .02em; }}
.bg-top .brand b {{ color: #8fe03a; }}
.bg-top .name {{ font-family: 'Outfit', sans-serif; font-weight: 600; font-size: 19px; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; overflow-x: auto; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; padding: 10px 14px; }}
.stTabs [aria-selected="true"] {{ color: {INDIGO}; }}
.bg-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #5d5b7a; font-weight: 700; margin: 18px 0 6px; }}
.bg-quote {{ margin: 0; padding: 12px 16px; background: #ebe9fb; border-left: 5px solid {INDIGO}; border-radius: 0 8px 8px 0; font-size: 16px; }}
.bg-commit {{ background: #e6f3d6; border-radius: 8px; padding: 10px 14px; }}
.bg-commit b {{ font-family: 'Outfit', sans-serif; color: #3f7d12; margin-right: 10px; }}
.bg-tag {{ display: inline-block; border-radius: 4px; padding: 1px 8px; font-size: 12px; font-weight: 700; text-transform: uppercase;
          letter-spacing: .05em; margin-right: 6px; }}
.bg-tag.nuevo, .bg-tag.refina, .bg-tag.cubierto {{ background: #e6f3d6; color: #3f7d12; }}
.bg-tag.contradice {{ background: #fde7e5; color: #b3261e; }}
.bg-tag.incierto, .bg-tag.divide, .bg-tag.fusiona {{ background: #fff0d9; color: #a35a00; }}
.bg-tag.ok {{ background: {GREEN}; color: #10270a; }}
.bg-tag.no {{ background: #fde7e5; color: #b3261e; }}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def top_band(title: str) -> None:
    st.markdown(f'<div class="bg-top"><span class="brand">CFO<b>TECH</b></span><span class="name">{title}</span></div>', unsafe_allow_html=True)
