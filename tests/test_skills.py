"""Skills en formato Agent Skills (clase 10): una por rol, con divulgación progresiva y sin conceder permisos."""
import pytest

from backlogguard.agents.requerimientos import INSTRUCTIONS_PATH as PRODUCER_RULES
from backlogguard.skills import SkillLoader, skill_instructions
from backlogguard.tools import ToolPolicy

ROLES = ("supervisor", "requerimientos", "critico", "auditor", "integracion")


def write_skill(root, name, front, body="# Cuerpo\nInstrucciones."):
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\n{front}\n---\n{body}\n", encoding="utf-8")
    return folder


def test_hay_una_skill_por_rol_con_nombre_y_version():
    loader = SkillLoader()
    summaries = {row["role"]: row for row in loader.list_summaries()}
    assert set(summaries) == set(ROLES)
    assert all(row["version"] == "1" and row["description"] for row in summaries.values())
    for role in ROLES:
        skill = loader.for_role(role)
        assert skill is not None and skill.name == summaries[role]["name"] and skill.instructions


def test_el_nivel_1_lee_solo_el_encabezado():
    loader = SkillLoader()
    loader.list_summaries()
    assert {e["event"] for e in loader.events} == {"metadata_read"}  # sin cargar ningún cuerpo
    loader.load("revision-adversarial")
    assert loader.events[-1] == {"event": "skill_body_load", "skill": "revision-adversarial"}


def test_una_skill_no_concede_permisos(tmp_path):
    write_skill(tmp_path, "skill-con-permisos", 'name: skill-con-permisos\ndescription: "x"\nallowed-tools: write_file')
    with pytest.raises(ValueError, match="no concede permisos"):
        SkillLoader(tmp_path).list_summaries()
    # y ninguna de las skills reales declara permisos ni cambia lo que ve cada rol
    assert all("allowed-tools" not in (p / "SKILL.md").read_text(encoding="utf-8") for p in SkillLoader().root.iterdir())
    assert ToolPolicy().allowed_tools_from_list is not None  # la autoridad sigue en código


def test_el_nombre_debe_coincidir_con_la_carpeta_y_ser_kebab_case(tmp_path):
    write_skill(tmp_path, "una-skill", 'name: otra-skill\ndescription: "x"')
    with pytest.raises(ValueError, match="coincidir"):
        SkillLoader(tmp_path).list_summaries()
    write_skill(tmp_path, "Mala_Skill", 'name: Mala_Skill\ndescription: "x"')
    with pytest.raises(ValueError, match="inválido"):
        SkillLoader(tmp_path).load("Mala_Skill")


def test_un_recurso_no_puede_salir_de_la_carpeta_de_la_skill(tmp_path):
    folder = write_skill(tmp_path, "mi-skill", 'name: mi-skill\ndescription: "x"')
    (folder / "references").mkdir()
    (folder / "references" / "lista.md").write_text("contenido", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("no", encoding="utf-8")
    loader = SkillLoader(tmp_path)
    assert loader.load_resource("mi-skill", "references/lista.md") == "contenido"
    with pytest.raises(ValueError, match="fuera"):
        loader.load_resource("mi-skill", "../secreto.txt")
    with pytest.raises(ValueError, match="carpeta directa"):
        loader.load("../mi-skill")


def test_el_prompt_del_agente_une_sus_reglas_y_la_skill_de_su_rol():
    text = skill_instructions("requerimientos", PRODUCER_RULES)
    assert "Agente de Requerimientos" in text and "Skill del rol: redaccion-de-historias" in text
    assert "requisitos distintos" in text and "ya_redactadas" in text and "posible duplicado" in text
    # las reglas duras no pasaron a la skill: siguen en el agent.md
    assert "línea base" in PRODUCER_RULES.read_text(encoding="utf-8") and "No cites nada que no hayas recuperado" in text
