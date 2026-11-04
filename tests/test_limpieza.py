"""Limpieza de la preventa: solo se elimina texto, las citas siguen siendo textuales y las páginas conservan su número."""
import pytest

from backlogguard.rag.compromisos import split_pages as commitment_pages
from backlogguard.rag.importers import ImportedSource, SourceImportError
from backlogguard.rag.limpieza import PageSpecError, aplicar, informe_markdown, limpiar, parse_pages

PORTADA = "Plataforma de Gestión Integral\nJunio - 2026\n1"
MODULO = (
    "Maestro de nodos\n- Crear, editar y eliminar nodos\nFEATURE\nStack Tecnológico\n- Descripción\n"
    "FEATURE\nIntegraciones a desarrollar\n- Descripción de API que se desarrolla\n"
    "FEATURE\nProcesos automáticos\n- Ver slide de procesos automáticos\n6"
)
ALCANCE = "Alcance incluido: la impresión de las piezas se realizará de forma manual por el equipo de Nortex.\nwww.ejemplo.com\n31"
SLA = "Soporte Post Implementación\nSLA Alta: 12 horas hábiles\n44"
HEADER = "Arquitectura e integraciones"
DOC = "\n\n".join(f"[[página {n}]]\n{body}" for n, body in [(1, PORTADA), (6, MODULO), (31, ALCANCE), (44, SLA)]) + "\n"


def test_parsea_paginas_y_rangos():
    assert parse_pages("1,2, 4;35-37") == {1, 2, 4, 35, 36, 37}
    assert parse_pages("") == set() and parse_pages(None) == set()
    with pytest.raises(PageSpecError, match="no existe la 60"):
        parse_pages("3,60", total=56)
    with pytest.raises(PageSpecError, match="No entiendo"):
        parse_pages("uno")
    with pytest.raises(PageSpecError, match="no es válido"):
        parse_pages("9-3")


def test_quita_la_plantilla_y_deja_el_contenido():
    page = commitment_pages(limpiar(DOC).text)
    assert page[6] == "Maestro de nodos\n- Crear, editar y eliminar nodos"
    assert page[31] == "Alcance incluido: la impresión de las piezas se realizará de forma manual por el equipo de Nortex."
    assert "6" not in page[6].split() and "FEATURE" not in limpiar(DOC).text


def test_sin_ruido_solo_excluye_paginas():
    result = limpiar(DOC, {1}, quitar_ruido=False)
    assert "FEATURE" in result.text and "[[página 1]]" not in result.text


def test_las_paginas_excluidas_no_aparecen_y_las_demas_conservan_su_numero():
    result = limpiar(DOC, {1, 44})
    assert result.excluded == [1, 44] and result.kept == [6, 31]
    assert sorted(commitment_pages(result.text)) == [6, 31]  # la 31 sigue siendo la 31, no la 2


def test_toda_linea_que_queda_figura_en_el_original():
    """La garantía de las citas: limpiar solo elimina, nunca reescribe."""
    original = {line.strip() for line in DOC.splitlines()}
    for result in (limpiar(DOC), limpiar(DOC, {1, 44}), limpiar(DOC, quitar_encabezados=True)):
        assert {line.strip() for line in result.text.splitlines() if line.strip()} <= original


def test_los_encabezados_repetidos_solo_se_quitan_si_se_pide():
    pages = [(n, f"{HEADER}\nContenido distinto de la página {n}") for n in range(1, 8)]
    doc = "\n\n".join(f"[[página {n}]]\n{body}" for n, body in pages) + "\n"
    assert limpiar(doc).text.count(HEADER) == 7  # por defecto no se toca: puede ser un rótulo con sentido
    assert HEADER not in limpiar(doc, quitar_encabezados=True).text
    assert limpiar(doc, quitar_encabezados=True).text.count("Contenido distinto") == 7


def test_el_informe_cuenta_palabras_y_lista_lo_quitado():
    report = informe_markdown(limpiar(DOC, {1, 44}), titulo="Limpieza de prueba")
    assert "# Limpieza de prueba" in report and "conservadas: 2 · excluidas: 2" in report
    assert "| 1 | 8 | 0 | excluida |" in report and "(3×) FEATURE" in report and "Stack Tecnológico" in report
    assert "las páginas conservan su número" in report


def test_aplicar_devuelve_una_fuente_lista_para_guardar():
    imported = ImportedSource(text=DOC, layout="paginas", words=len(DOC.split()), pages=44, warnings=["2 página(s) casi sin texto (portadas o imágenes): [1]."])
    clean, detail = aplicar(imported, {1, 44})
    assert clean.layout == "paginas" and clean.pages == 44 and clean.words == detail.words < imported.words
    assert clean.words == len(clean.text.replace("[[página 6]]", "").replace("[[página 31]]", "").split())
    assert any("Se conservaron las páginas 6, 31" in w for w in clean.warnings) and not any("casi sin texto" in w for w in clean.warnings)


def test_no_deja_excluir_todo_ni_una_pagina_que_no_existe():
    imported = ImportedSource(text=DOC, layout="paginas", words=10, pages=44)
    with pytest.raises(SourceImportError, match="no queda ninguna página"):
        aplicar(imported, {1, 6, 31, 44})
    with pytest.raises(PageSpecError, match="no tiene la página 2"):
        aplicar(imported, {2})


def test_un_texto_sin_paginas_marcadas_no_se_puede_limpiar():
    with pytest.raises(SourceImportError, match="páginas marcadas"):
        limpiar("Reunión en formato de diálogo, sin páginas.")
