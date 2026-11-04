"""Minutas en Word (.docx): se leen en orden, las tablas no se confunden con oradores y los errores son claros."""
from io import BytesIO

import pytest
from docx import Document

from backlogguard.rag.importers import SourceImportError, import_docx


def build(fill) -> bytes:
    document = Document()
    fill(document)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def minuta(document):
    document.add_heading("Minuta de reunión", level=1)
    document.add_paragraph("Proyecto: Portal de clientes")
    document.add_paragraph("Fecha: 2026-10-20")
    table = document.add_table(rows=3, cols=2)
    for row, (name, role) in zip(table.rows, [("Participante", "Rol"), ("Laura Gómez", "Product Owner"), ("Marcos Díaz", "Service Manager")]):
        row.cells[0].text, row.cells[1].text = name, role
    document.add_paragraph("Laura Gómez: Necesitamos que el reporte mensual salga en Excel.")
    document.add_paragraph("Marcos Díaz: Entendido, lo sumamos al alcance.")
    actions = document.add_table(rows=2, cols=3)
    for row, values in zip(actions.rows, [("Acción", "Responsable", "Fecha"), ("Enviar el diseño del reporte", "Marcos Díaz", "2026-10-27")]):
        for cell, value in zip(row.cells, values):
            cell.text = value


def test_una_minuta_word_se_importa_con_sus_oradores_y_roles():
    imported = import_docx(build(minuta))
    assert imported.layout == "dialogo" and imported.detected["proyecto"] == "Portal de clientes"
    assert imported.speakers == ["Laura Gómez (Product Owner)", "Marcos Díaz (Service Manager)"]
    assert "Laura Gómez (Product Owner): Necesitamos que el reporte mensual salga en Excel." in imported.text
    assert not imported.warnings


def test_una_tabla_de_acciones_queda_como_nota_y_no_como_un_orador():
    imported = import_docx(build(minuta))
    assert "Acción – Enviar el diseño del reporte; Responsable – Marcos Díaz; Fecha – 2026-10-27" in imported.text
    assert all(not speaker.startswith("Acción") for speaker in imported.speakers)


def test_una_minuta_sin_dialogo_se_importa_como_nota_y_avisa():
    def resumen(document):
        document.add_paragraph("Se acordó incorporar el reporte mensual en Excel y postergar la app móvil.")
        document.add_paragraph("Próximo paso: validar el alcance con el cliente")

    imported = import_docx(build(resumen))
    assert "reporte mensual en Excel" in imported.text and any("sin oradores" in w for w in imported.warnings)


def test_un_archivo_que_no_es_word_se_rechaza_con_un_mensaje_claro():
    with pytest.raises(SourceImportError, match="docx"):
        import_docx(b"esto no es un zip")


def test_un_word_vacio_se_rechaza():
    with pytest.raises(SourceImportError, match="no tiene texto"):
        import_docx(build(lambda document: None))


def prosa(document):
    """Una minuta formal: datos en una tabla, temas con rótulos «Algo: texto» y acuerdos en otra tabla. Nadie 'habla'."""
    document.add_heading("Minuta de reunión", level=1)
    facts = document.add_table(rows=3, cols=2)
    for row, (key, value) in zip(facts.rows, [("Fecha", "24-08-2026"), ("Hora", "14.00"), ("Lugar", "Teams")]):
        row.cells[0].text, row.cells[1].text = key, value
    convocados = document.add_table(rows=3, cols=1)
    for row, value in zip(convocados.rows, ["Convocados a la reunión", "Persona Uno (Empresa A)", "Persona Dos (Empresa B)"]):
        row.cells[0].text = value
    document.add_paragraph("Tema #1: Definición de la Entidad Elección")
    document.add_paragraph("Las elecciones se configuran como entidades aisladas e independientes.")
    document.add_paragraph("Acuerdo sobre creación: El Super Admin puede crear todas las elecciones.")
    acuerdos = document.add_table(rows=2, cols=1)
    for row, value in zip(acuerdos.rows, ["Acuerdos de la reunión", "Acuerdo #1: Las elecciones son ambientes independientes."]):
        row.cells[0].text = value


def test_una_minuta_en_prosa_conserva_los_parrafos_y_no_inventa_oradores():
    imported = import_docx(build(prosa))
    lines = imported.text.splitlines()
    assert imported.speakers == [] and imported.layout == "dialogo"
    assert all(line.startswith("Nota de la minuta: ") for line in lines)
    assert "Nota de la minuta: Tema #1: Definición de la Entidad Elección" in lines  # el rótulo no se vuelve un orador
    assert "Nota de la minuta: Acuerdo sobre creación: El Super Admin puede crear todas las elecciones." in lines
    assert len(lines) >= 9 and any("Minuta en prosa" in w for w in imported.warnings)


def test_los_datos_de_la_reunion_quedan_uno_por_linea_y_las_listas_de_una_columna_tambien():
    text = import_docx(build(prosa)).text
    for line in ("Fecha – 24-08-2026", "Hora – 14.00", "Lugar – Teams", "Convocados a la reunión", "Persona Uno (Empresa A)", "Acuerdo #1: Las elecciones son ambientes independientes."):
        assert f"Nota de la minuta: {line}" in text.splitlines()


def test_una_minuta_en_prosa_se_parte_en_fragmentos_por_parrafo():
    from backlogguard.rag.chunking import build_chunks

    imported = import_docx(build(prosa))
    chunks = build_chunks("m", imported.text, {"layout": imported.layout, "source_name": "M", "source_type": "minuta", "source_date": "2026-08-24"})
    assert len(chunks) >= 2 and any("Super Admin puede crear" in c["text"] for c in chunks)
