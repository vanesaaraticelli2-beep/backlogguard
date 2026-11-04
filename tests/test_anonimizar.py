"""Anonimización: alias fijos para empresas y personas, datos de contacto y las fuentes ya importadas."""
import pytest

from backlogguard.rag.anonimizar import Diccionario, DictionaryError, Regla, anonimizar, anonimizar_nombre, aplicar, cargar, resumen
from backlogguard.rag.importers import ImportedSource

DIC = Diccionario((
    Regla(("Nortex", "Nortx"), "LogiCorp"),
    Regla(("CFOTech", "CFO Tech"), "TechPartner"),
    Regla(("Carlos Gómez", "Gómez"), "Persona 1"),
    Regla(("Juan De Luca",), "Persona 4"),
))


def test_reemplaza_sin_importar_mayusculas_ni_variantes():
    result = anonimizar("NORTEX contrata a CFOTech. Nortx, nortex y cfo tech.", DIC)
    assert result.text == "LogiCorp contrata a TechPartner. LogiCorp, LogiCorp y TechPartner."
    assert result.reemplazos == {"LogiCorp": 3, "TechPartner": 2}


def test_un_nombre_partido_por_un_salto_de_linea_se_reemplaza_igual():
    assert anonimizar("Convoca Juan De\nLuca (Nortex)", DIC).text == "Convoca Persona 4 (LogiCorp)"


def test_no_toca_palabras_que_solo_contienen_el_termino():
    assert anonimizar("el nortexismo y los gomez-fans", DIC).text.startswith("el nortexismo")
    assert anonimizar("MiNortex", DIC).text == "MiNortex"


def test_el_nombre_completo_gana_al_apellido_solo():
    assert anonimizar("Carlos Gómez y su colega Gómez", DIC).text == "Persona 1 y su colega Persona 1"


def test_oculta_correos_direcciones_web_telefonos_y_usuarios():
    text = "Escribir a info@ejemplotech.com o ver www.ejemplotech.com, tel +54 9 11 5555-0000, redes @ejemplotech."
    result = anonimizar(text, DIC)
    assert "ejemplotech" not in result.text.lower() and "5555" not in result.text
    assert "correo@ejemplo.com" in result.text and "www.ejemplo.com" in result.text and "@usuario" in result.text
    assert sum(result.genericos.values()) == 4


def test_avisa_de_numeros_largos_y_de_posibles_nombres_que_faltan():
    result = anonimizar("El DNI 30123456 de Marina Quiroga. Marina Quiroga firmó. Quiroga cobró.", DIC)
    assert any("número(s) largo(s)" in a for a in result.avisos)
    assert any(c.startswith("Quiroga") or c.startswith("Marina") for c in result.revisar)


def test_es_idempotente():
    once = anonimizar("Nortex y Carlos Gómez", DIC).text
    assert anonimizar(once, DIC).text == once


def test_un_alias_no_puede_contener_un_termino_que_tambien_se_reemplaza():
    with pytest.raises(DictionaryError, match="contiene el término"):
        Diccionario((Regla(("Nortex",), "Nortex SA"),))
    with pytest.raises(DictionaryError):
        Diccionario((Regla((), "X"),))


def test_carga_el_diccionario_desde_yaml(tmp_path):
    path = tmp_path / "d.yaml"
    path.write_text("reemplazos:\n  - buscar: [Acme, ACME SA]\n    por: Cliente X\n  - buscar: Juan Pérez\n    por: Persona 1\n", encoding="utf-8")
    assert anonimizar("Juan Perez trabaja en acme sa", cargar(path)).text == "Persona 1 trabaja en Cliente X"  # sin importar las tildes
    path.write_text("reemplazos: []\n", encoding="utf-8")
    with pytest.raises(DictionaryError, match="al menos una regla"):
        cargar(path)
    with pytest.raises(DictionaryError, match="No se pudo leer"):
        cargar(tmp_path / "no-existe.yaml")


def test_aplica_a_la_fuente_importada_a_sus_oradores_y_al_nombre():
    imported = ImportedSource(
        text="[[página 3]]\nNortex requiere una plataforma.\n", layout="paginas", words=5, pages=3,
        speakers=["Carlos Gómez (CFOTech)"], detected={"proyecto": "Nortex Elecciones"}, warnings=["x"],
    )
    clean, result = aplicar(imported, DIC)
    assert clean.text == "[[página 3]]\nLogiCorp requiere una plataforma.\n" and clean.layout == "paginas" and clean.pages == 3
    assert clean.speakers == ["Persona 1 (TechPartner)"] and clean.detected == {"proyecto": "LogiCorp Elecciones"}
    assert clean.warnings[0] == "x" and "Anonimizada: LogiCorp (1×)" in clean.warnings[1]
    assert anonimizar_nombre("Propuesta CFOTech - Proyecto Nortex", DIC) == "Propuesta TechPartner - Proyecto LogiCorp"
    assert resumen(result) == "LogiCorp (1×)"


def test_nada_que_reemplazar_se_dice():
    assert resumen(anonimizar("Un texto cualquiera", DIC)) == "no se reemplazó nada"
