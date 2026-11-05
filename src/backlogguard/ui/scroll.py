"""Al decidir, la pantalla sube sola hasta el título de lo que sigue (Streamlit conserva el scroll al recargar).

Cada pantalla marca el comienzo de lo que se decide con `anchor(nombre)`. Al decidir se llama a `request_scroll(nombre)`;
en la recarga siguiente, `apply_scroll(nombre)` escribe un script chico que lleva la vista hasta esa marca.
"""
from __future__ import annotations

import streamlit as st

REVIEW = "bg-detail-top"
DECISION = "bg-decision-top"


def _key(name: str) -> str:
    return f"_scroll_{name}"


def anchor(name: str) -> None:
    st.markdown(f'<div id="{name}" class="bg-anchor"></div>', unsafe_allow_html=True)


def request_scroll(name: str) -> None:
    st.session_state[_key(name)] = True


def apply_scroll(name: str) -> None:
    """Si hay un pedido pendiente para `name`, lo consume y sube hasta la marca (reintenta mientras la pantalla termina de armarse)."""
    if not st.session_state.pop(_key(name), False):
        return
    st.html(
        f"""<script>
        (function () {{
          var tries = 0;
          function go() {{
            var el = document.getElementById("{name}");
            if (el) {{ el.scrollIntoView({{block: "start", behavior: "auto"}}); }}
            if (tries++ < 8) {{ setTimeout(go, 150); }}
          }}
          go();
        }})();
        </script>""",
        unsafe_allow_javascript=True,
    )
