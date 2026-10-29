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
.stApp {{ font-family: 'Source Sans 3', 'Segoe UI', sans-serif; }}
button, input, textarea, select {{ font-family: inherit; }}
[data-testid="stIconMaterial"], [data-testid="stIconMaterial"] * {{ font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important; }}
h1, h2, h3, h4 {{ font-family: 'Outfit', 'Segoe UI', sans-serif; color: {INDIGO}; }}
.bg-top {{ background: {INDIGO}; border-bottom: 5px solid {GREEN}; border-radius: 8px; padding: 14px 20px; margin-bottom: 8px;
          display: flex; flex-wrap: wrap; align-items: center; gap: 8px 24px; color: #fff; }}
.bg-top .brand {{ font-family: 'Outfit', sans-serif; font-weight: 700; font-size: 22px; letter-spacing: .02em; }}
.bg-top .brand b {{ color: #8fe03a; }}
.bg-top .name {{ font-family: 'Outfit', sans-serif; font-weight: 600; font-size: 19px; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; overflow-x: auto; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; padding: 10px 14px; }}
.stTabs [aria-selected="true"] {{ color: {INDIGO}; }}
.bg-steps {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 10px; }}
.bg-step {{ flex: 1 1 130px; display: flex; flex-direction: column; padding: 6px 12px; border-radius: 8px; background: #f1f0f8; color: #5d5b7a; border-bottom: 4px solid #d9d7ee; }}
.bg-step small {{ font-size: 12px; }}
.bg-step.done {{ background: #e6f3d6; color: #3f7d12; border-bottom-color: {GREEN}; }}
.bg-step.now {{ background: {INDIGO}; color: #fff; border-bottom-color: {GREEN}; }}
.bg-next {{ background: #eef0ff; border-left: 6px solid {INDIGO}; border-radius: 0 8px 8px 0; padding: 10px 16px; font-size: 16px; }}
.bg-next span {{ font-family: 'Outfit', sans-serif; font-weight: 700; color: {INDIGO}; text-transform: uppercase; font-size: 12px; letter-spacing: .08em; margin-right: 8px; }}
.bg-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #5d5b7a; font-weight: 700; margin: 18px 0 6px; }}
.bg-quote {{ margin: 0; padding: 12px 16px; background: #ebe9fb; border-left: 5px solid {INDIGO}; border-radius: 0 8px 8px 0; font-size: 16px; }}
.bg-commit {{ background: #e6f3d6; border-radius: 8px; padding: 10px 14px; }}
.bg-commit b {{ font-family: 'Outfit', sans-serif; color: #3f7d12; margin-right: 10px; }}
.bg-tag {{ display: inline-block; border-radius: 4px; padding: 1px 8px; font-size: 12px; font-weight: 700; text-transform: uppercase;
          letter-spacing: .05em; margin-right: 6px; }}
.bg-tag.nuevo, .bg-tag.refina, .bg-tag.cubierto {{ background: #e6f3d6; color: #3f7d12; }}
.bg-tag.contradice {{ background: #fde7e5; color: #b3261e; }}
.bg-tag.incierto, .bg-tag.divide, .bg-tag.fusiona {{ background: #fff0d9; color: #a35a00; }}
.us {{ max-width: 920px; border: 1px solid #9fa8c4; margin: 4px 0 10px; font-family: Arial, 'Segoe UI', sans-serif; }}
.us-banner {{ background: #4b4ba0; color: #fff; font-weight: 700; font-size: 20px; text-align: center; padding: 12px; }}
.us-head {{ display: grid; grid-template-columns: 110px 1fr; border-top: 1px solid #9fa8c4; }}
.us-id {{ background: #5b6b7b; color: #fff; font-weight: 700; font-size: 18px; text-align: center; padding: 10px 6px; }}
.us-title {{ background: #4b4ba0; color: #fff; font-weight: 700; font-size: 16px; padding: 10px 14px; overflow-wrap: anywhere; }}
.us-row {{ display: grid; grid-template-columns: 110px 1fr; background: #dde6f5; border-top: 1px solid #9fa8c4; color: #000; }}
.us-feature {{ display: block; padding: 8px 14px; color: #1f2a6b; }}
.us-label {{ background: #b4b7dc; color: #fff; font-weight: 700; padding: 8px 10px; }}
.us-text {{ padding: 8px 14px; overflow-wrap: anywhere; }}
.us-criteria {{ background: #7db383; color: #fff; font-weight: 700; padding: 8px 14px; border-top: 1px solid #9fa8c4; }}
.us-check {{ color: #2e9e5b; font-weight: 700; font-size: 20px; text-align: center; padding: 6px 4px; }}
.bg-chat {{ display: grid; gap: 10px; margin: 8px 0 16px; }}
.bg-msg {{ background: #fff; border: 1px solid #dddcec; border-left: 6px solid var(--c); border-radius: 8px; padding: 10px 14px; max-width: 920px; }}
.bg-msg.warn {{ background: #fffaf0; }}
.bg-msg.wait {{ background: #eef0ff; border-style: dashed; border-left-style: solid; }}
.bg-head {{ font-size: 13px; color: #5d5b7a; }}
.bg-head b {{ color: var(--c); font-family: 'Outfit', sans-serif; font-size: 15px; }}
.bg-text {{ margin-top: 2px; overflow-wrap: anywhere; }}
.bg-scroll {{ max-height: 520px; overflow-y: auto; display: flex; flex-direction: column-reverse; padding-right: 6px; border: 1px solid #dddcec; border-radius: 10px; background: #fbfbfe; }}
.bg-scroll .bg-chat {{ margin: 0; padding: 10px; }}
.bg-status {{ display: flex; align-items: center; gap: 10px; border-radius: 8px; padding: 10px 16px; font-weight: 700; font-size: 16px; margin: 4px 0 10px; }}
.bg-status .dot {{ width: 12px; height: 12px; border-radius: 50%; background: currentColor; flex: none; }}
.bg-status.ok {{ background: #e6f3d6; color: #2f6a0a; }}
.bg-status.paused {{ background: #fde7e5; color: #b3261e; }}
.bg-status.warn {{ background: #fff0d9; color: #a35a00; }}
.bg-msg ul {{ margin: 6px 0 0; padding-left: 20px; }}
.bg-q {{ margin: 8px 0 0; padding: 6px 12px; background: #ebe9fb; border-left: 4px solid #13056D; border-radius: 0 6px 6px 0; font-size: 14px; }}
.bg-q small {{ display: block; color: #5d5b7a; margin-top: 2px; }}
.bg-tag.ok {{ background: {GREEN}; color: #10270a; }}
.bg-tag.no {{ background: #fde7e5; color: #b3261e; }}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def top_band(title: str) -> None:
    st.markdown(f'<div class="bg-top"><span class="brand">CFO<b>TECH</b></span><span class="name">{title}</span></div>', unsafe_allow_html=True)
