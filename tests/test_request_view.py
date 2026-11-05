from backlogguard.ui.request_view import headline, label_for, parse_objections, short_refs

SUMMARY = (
    "El Crítico y el productor no llegaron a un acuerdo en 2 rondas.\nObjeciones vigentes:\n"
    "- El tercer criterio no tiene respaldo en las citas del ítem. La única cita (minuta_logicorp_24_08_2026:dialogo:006:82daaec7) solo dice otra cosa.\n"
    "- Falta un escenario. Ningún criterio cubre el caso del candado."
)


def test_short_refs_acorta_los_ids_de_fragmento():
    assert short_refs("ver minuta_logicorp_24_08_2026:dialogo:006:82daaec7 y listo") == "ver [24-08, frag. 6] y listo"
    assert short_refs("sin ids") == "sin ids"


def test_parse_objections_separa_las_objeciones():
    items = parse_objections(SUMMARY)
    assert len(items) == 2 and items[0].startswith("El tercer criterio") and items[1].startswith("Falta un escenario")
    assert parse_objections("Otro tipo de pedido") is None


def test_parse_objections_une_las_lineas_partidas():
    assert parse_objections("El Crítico y el productor no llegaron a un acuerdo.\n- uno\ncontinúa\n- dos") == ["uno continúa", "dos"]


def test_headline_deja_lo_esencial_y_el_detalle():
    first, rest = headline(parse_objections(SUMMARY)[0])
    assert first == "El tercer criterio no tiene respaldo en las citas del ítem."
    assert rest.startswith("La única cita ([24-08, frag. 6])")
    assert headline("Corto.") == ("Corto.", "")


def test_label_for_clasifica():
    assert label_for("Falta un escenario. Nada cubre X")[0] == "Falta un escenario"
    assert label_for("La minuta posterior choca con el criterio")[0] == "Choca con otra reunión"
    assert label_for("No tiene respaldo en las citas")[0] == "Falta respaldo en la cita"
    assert label_for("Otra cosa")[0] == "Objeción"
