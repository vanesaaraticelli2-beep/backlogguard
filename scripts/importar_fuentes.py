"""Importa tu preventa (PDF) y la transcripción de una reunión (texto) como fuentes de BacklogGuard.

    .venv\\Scripts\\python scripts\\importar_fuentes.py --listar
    .venv\\Scripts\\python scripts\\importar_fuentes.py ^
        --preventa entrada\\preventa.pdf --preventa-nombre "Propuesta comercial CFOTech" --preventa-fecha 2025-10-01 ^
        --reunion entrada\\inception.txt --reunion-nombre "Inception" --reunion-fecha 2026-01-25
    .venv\\Scripts\\python scripts\\importar_fuentes.py --borrar inception
    .venv\\Scripts\\python scripts\\importar_fuentes.py --limpiar          # vuelve a las fuentes de ejemplo

Las fuentes quedan en `data/fuentes/` (no se suben a git). Mientras haya al menos una preventa y una reunión
ahí, las corridas usan esas fuentes en lugar de las de ejemplo. Los documentos no se envían a ningún modelo
en este paso: solo se leen y se guardan.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from backlogguard.board import SourceType
from backlogguard.graph.setup import has_user_sources, user_sources_dir
from backlogguard.rag import SourceLibrary, build_chunks
from backlogguard.rag.importers import ImportedSource, SourceImportError, estimate, import_pdf, import_transcript
from backlogguard.rag.sources import SourceMetadata, slugify

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = SourceLibrary(user_sources_dir(ROOT / "data"))


def save(imported: ImportedSource, name: str, kind: SourceType, when: date, *, overwrite: bool) -> str:
    metadata = SourceMetadata(source_name=name, source_type=kind, source_date=when, layout=imported.layout)
    document_id = slugify(name)
    LIBRARY.write(document_id, metadata, imported.text, overwrite=overwrite)
    chunks = build_chunks(document_id, imported.text, metadata.model_dump(mode="json"))
    size = estimate(imported.words)
    print(f"\n✔ {document_id}: {kind.value}, {when.isoformat()}, {imported.words} palabras (~{size['tokens']} tokens), {len(chunks)} fragmentos")
    if imported.pages:
        print(f"   {imported.pages} páginas")
    if imported.speakers:
        print("   oradores: " + "; ".join(imported.speakers))
    if imported.detected:
        print(f"   encabezado del documento: {imported.detected}")
    for warning in imported.warnings:
        print(f"   ⚠ {warning}")
    print("   vista previa: " + " ".join(imported.text.split())[:240] + "…")
    return document_id


def listing() -> None:
    entries = LIBRARY.describe() if LIBRARY.root.is_dir() else []
    print(f"Fuentes propias en {LIBRARY.root.relative_to(ROOT)}: {len(entries)}")
    for document_id, meta in entries:
        print(f"  {document_id:40} {meta.source_type.value:9} {meta.source_date} {meta.layout:8} {meta.source_name}")
    print("Las corridas usan: " + ("estas fuentes propias" if has_user_sources(LIBRARY.root) else "las fuentes de ejemplo (faltan una preventa y una reunión propias)"))


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("La fecha debe ser AAAA-MM-DD (por ejemplo 2026-01-25).") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preventa", type=Path)
    parser.add_argument("--preventa-nombre")
    parser.add_argument("--preventa-fecha", type=parse_date)
    parser.add_argument("--reunion", type=Path)
    parser.add_argument("--reunion-nombre")
    parser.add_argument("--reunion-fecha", type=parse_date)
    parser.add_argument("--tipo", choices=["reunion", "minuta"], default="reunion")
    parser.add_argument("--sobrescribir", action="store_true")
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--borrar", metavar="ID")
    parser.add_argument("--limpiar", action="store_true")
    options = parser.parse_args()

    if options.limpiar:
        for document_id, _ in (LIBRARY.describe() if LIBRARY.root.is_dir() else []):
            LIBRARY.delete(document_id)
        print("Fuentes propias borradas: las corridas vuelven a usar las de ejemplo.")
        return 0
    if options.borrar:
        print("Borrada." if LIBRARY.delete(options.borrar) else "No existe esa fuente.")
        return 0
    if options.listar and not (options.preventa or options.reunion):
        listing()
        return 0

    jobs = []
    if options.preventa:
        jobs.append((options.preventa, options.preventa_nombre, options.preventa_fecha, SourceType.PREVENTA, import_pdf))
    if options.reunion:
        jobs.append((options.reunion, options.reunion_nombre, options.reunion_fecha, SourceType(options.tipo), import_transcript))
    if not jobs:
        parser.print_help()
        return 1
    for path, name, when, kind, importer in jobs:
        if not name or when is None:
            print(f"Para importar {path.name} indicá el nombre y la fecha (AAAA-MM-DD).")
            return 1
        try:
            save(importer(path), name, kind, when, overwrite=options.sobrescribir)
        except (SourceImportError, FileExistsError, OSError) as exc:
            print(f"✘ {path.name}: {exc}")
            return 1
    print()
    listing()
    return 0


if __name__ == "__main__":
    sys.exit(main())
