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
