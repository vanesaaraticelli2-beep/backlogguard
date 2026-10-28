"""Transcripciones WebVTT (Teams, Zoom, Meet), lectura sin requisitos y limpieza al borrar una fuente."""
from datetime import date

import pytest
from test_catalogo import draft, evidence, proposal
from test_continuidad import CUIT, SCORE, answer, run, world  # noqa: F401  (fixture)

from backlogguard.catalog import Catalog, ProposalKind, ProposalState
from backlogguard.rag.importers import import_transcript, is_vtt, vtt_to_dialogue
from backlogguard.ui.app import date_from_filename

TEAMS = """﻿WEBVTT

NOTE grabación de ejemplo

79b8b456-600a/6-0
00:00:10.842 --> 00:00:11.362
<v ANA PEREZ>Cristal.</v>

79b8b456-600a/19-0
00:01:00.082 --> 00:01:03.190
<v ANA PEREZ>Bueno,
hoy hay que validar el CUIT</v>

79b8b456-600a/19-1
00:01:03.190 --> 00:01:07.040
<v ANA PEREZ>antes de crear la cuenta.</v>

79b8b456-600a/22-0
00:01:03.642 --> 00:01:05.993
<v FACUNDO CRUCE&#209;O>sí,
estoy de acuerdo</v>

79b8b456-600a/21-0
00:01:04.722 --> 00:01:06.002
<v LUIS GOMEZ>Yo también.</v>

79b8b456-600a/19-2
00:01:07.040 --> 00:01:09.202
<v ANA PEREZ>y avisar por mail.</v>

79b8b456-600a/22-1
00:01:09.993 --> 00:01:12.402
<v FACUNDO CRUCE&#209;O>con el <i>formulario</i> nuevo.</v>
"""


def test_se_reconoce_un_vtt_y_se_quita_todo_lo_que_no_es_conversacion():
    assert is_vtt(TEAMS) and not is_vtt("Ana: hola") and is_vtt("WEBVTT\n")
    text = vtt_to_dialogue(TEAMS)
    assert "WEBVTT" not in text and "-->" not in text and "grabación de ejemplo" not in text and "79b8b456" not in text and "<" not in text


def test_las_partes_de_una_frase_se_unen_aunque_otro_orador_la_interrumpa_y_se_ordena_por_inicio():
    lines = vtt_to_dialogue(TEAMS).strip().split("\n")
    assert lines == [
        "ANA PEREZ: Cristal. Bueno, hoy hay que validar el CUIT antes de crear la cuenta. y avisar por mail.",
        "FACUNDO CRUCEÑO: sí, estoy de acuerdo con el formulario nuevo.",
        "LUIS GOMEZ: Yo también.",
    ]


def test_los_acentos_codificados_y_las_etiquetas_de_formato_se_limpian_tambien_en_el_orador():
    imported = import_transcript(TEAMS.encode("utf-8"))
    assert "FACUNDO CRUCEÑO" in imported.speakers and "&#" not in imported.text and "<i>" not in imported.text
    assert imported.layout == "dialogo" and imported.words > 10 and imported.speakers == sorted(imported.speakers)


def test_un_vtt_estilo_zoom_toma_el_orador_del_prefijo_y_une_los_seguidos():
    zoom = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\nAna: Hola a todos.\n\n2\n00:00:03.500 --> 00:00:05.000\nAna: Empecemos.\n\n3\n00:00:05.100 --> 00:00:06.000\nLuis: Dale.\n"
    assert vtt_to_dialogue(zoom).strip().split("\n") == ["Ana: Hola a todos. Empecemos.", "Luis: Dale."]


def test_un_vtt_sin_oradores_se_importa_como_nota_con_aviso():
    plain = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHola a todos.\n\n00:00:03.500 --> 00:00:05.000\nEmpecemos ya.\n"
    imported = import_transcript(plain)
    assert imported.speakers == [] and any("sin oradores" in w for w in imported.warnings)
    assert "Hola a todos. Empecemos ya." in imported.text


def test_un_texto_normal_no_se_toca():
    assert import_transcript("Ana: Hola.\nLuis: Chau.\n").text == "Ana: Hola.\nLuis: Chau.\n"


def test_la_fecha_se_propone_desde_el_nombre_del_archivo_y_solo_si_es_valida():
    assert date_from_filename("2026-08-21 Daily Portal (1).vtt") == date(2026, 8, 21)
    assert date_from_filename("reunion.vtt") is None and date_from_filename("2026-13-45 x.vtt") is None


def test_una_lectura_sin_requisitos_avisa_y_no_marca_la_reunion_como_leida(world):  # noqa: F811
    result, _, classifier = run(world, [])
    assert result.nothing_found and result.candidates == [] and classifier.prompts == []
    assert world["catalog"].source_status("reunion_01", world["meeting"].fingerprint) == "nueva"
    again, _, _ = run(world, [CUIT], [answer({"tipo": "nuevo", "compromisos": ["C-001"]})])  # se puede volver a leer
    assert not again.nothing_found and world["catalog"].source_status("reunion_01", world["meeting"].fingerprint) == "procesada"


def test_borrar_una_fuente_olvida_su_lectura_y_sus_propuestas_sin_decidir_pero_no_lo_aprobado(tmp_path):
    catalog = Catalog(tmp_path / "c.sqlite")
    pending = catalog.propose(proposal(key="a", source_id="falsa", fp="f1"))
    approved = catalog.propose(proposal(key="b", source_id="falsa", fp="f1", drafts=[draft("Otro requisito distinto")]))
    catalog.decide(approved.id, approve=True, by="product_owner")
    catalog.apply(approved.id)
    catalog.mark_source_processed("falsa", "f1", date(2026, 10, 27))
    other = proposal(key="c", source_id="real", fp="r1", ev=[evidence(source_id="real", fp="r1")])
    catalog.propose(other)
    assert catalog.latest_processed_date(exclude="real") == date(2026, 10, 27)  # la reunión falsa dejaría a las demás «fuera de orden»
    assert catalog.forget_source("falsa") == 1
    assert catalog.latest_processed_date(exclude="real") is None
    assert catalog.source_status("falsa", "f1") == "nueva"
    assert [p.id for p in catalog.proposals(source_id="falsa")] == [approved.id] and catalog.proposal(approved.id).state is ProposalState.APLICADA
    assert len(catalog.requirements()) == 1 and catalog.proposals(source_id="real")[0].kind is ProposalKind.NUEVO
    assert pending.id not in [p.id for p in catalog.proposals()]
    with pytest.raises(KeyError):
        catalog.proposal(pending.id)
