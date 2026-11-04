r"""Informe de limpieza de una preventa en PDF, sin guardar nada y sin usar modelos (no cuesta).

    .venv\Scripts\python scripts\limpiar_preventa.py entrada\preventa.pdf
    .venv\Scripts\python scripts\limpiar_preventa.py entrada\preventa.pdf --excluir "1,2,4,35-56" --informe evals\real\limpieza_preventa.md

Muestra, página por página, cuántas palabras tiene y qué se quitaría (texto de plantilla, encabezados repetidos y las
páginas que indiques). Para guardar la preventa ya limpia, usá las mismas opciones en scripts/importar_fuentes.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backlogguard.rag.importers import SourceImportError, import_pdf
from backlogguard.rag.limpieza import PageSpecError, guardar_informe, informe_markdown, limpiar, parse_pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--excluir", default="", help="páginas a excluir, por ejemplo 1,2,4,35-56")
    parser.add_argument("--conservar-plantilla", action="store_true", help="no quitar el texto de plantilla ni los encabezados repetidos")
    parser.add_argument("--quitar-encabezados", action="store_true", help="también quitar líneas cortas que se repiten en muchas páginas (puede sacar rótulos con sentido)")
    parser.add_argument("--informe", type=Path, help="guarda el informe en este archivo (Markdown)")
    options = parser.parse_args()
    try:
        imported = import_pdf(options.pdf)
        cleaned = limpiar(imported.text, parse_pages(options.excluir, total=imported.pages), quitar_ruido=not options.conservar_plantilla, quitar_encabezados=options.quitar_encabezados)
    except (SourceImportError, PageSpecError, OSError) as exc:
        print(f"No se pudo: {exc}")
        return 1
    print(informe_markdown(cleaned, titulo=f"Limpieza de {options.pdf.name}"))
    if options.informe:
        print(f"Informe guardado en {guardar_informe(cleaned, options.informe, titulo=f'Limpieza de {options.pdf.name}')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
