r"""Prueba la anonimización sobre un documento SIN guardar nada y sin usar modelos (no cuesta).

    .venv\Scripts\python scripts\anonimizar.py "entrada\preventa.pdf" --excluir "1,2,4,35-56"
    .venv\Scripts\python scripts\anonimizar.py "C:\...\minuta.docx"
    .venv\Scripts\python scripts\anonimizar.py evals\real\esperados_minuta.md --salida evals\real\esperados_minuta.anonimo.md

Muestra qué se reemplazó y cuántas veces, las palabras con mayúscula que se repiten (posibles nombres que faltan en el
diccionario) y el comienzo del texto ya anonimizado. Con --salida guarda el texto anonimizado en un archivo.
El diccionario por defecto es evals/real/anonimizacion.yaml.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backlogguard.rag.anonimizar import DictionaryError, anonimizar, cargar, resumen
from backlogguard.rag.importers import SourceImportError, decode_text, import_docx, import_pdf
from backlogguard.rag.limpieza import PageSpecError, limpiar, parse_pages

ROOT = Path(__file__).resolve().parents[1]


def leer(path: Path, excluir: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        imported = import_pdf(path)
        return limpiar(imported.text, parse_pages(excluir, total=imported.pages)).text
    if suffix == ".docx":
        return import_docx(path).text
    return decode_text(path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--diccionario", type=Path, default=ROOT / "evals" / "real" / "anonimizacion.yaml")
    parser.add_argument("--excluir", default="", help="solo PDF: páginas a excluir antes de anonimizar")
    parser.add_argument("--salida", type=Path)
    options = parser.parse_args()
    try:
        text = leer(options.archivo, options.excluir)
        result = anonimizar(text, cargar(options.diccionario))
    except (SourceImportError, PageSpecError, DictionaryError, OSError) as exc:
        print(f"No se pudo: {exc}")
        return 1
    print(f"Reemplazos: {resumen(result)}")
    for warning in result.avisos:
        print(f"⚠ {warning}")
    print("Revisar (palabras con mayúscula que se repiten y no están en el diccionario): " + (", ".join(result.revisar) or "ninguna"))
    if options.salida:
        options.salida.parent.mkdir(parents=True, exist_ok=True)
        options.salida.write_text(result.text, encoding="utf-8")
        print(f"Texto anonimizado guardado en {options.salida}")
    print("\n--- comienzo del texto anonimizado ---\n" + result.text[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
