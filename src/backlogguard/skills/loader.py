"""Carga de Agent Skills (clase 10 del curso, adaptada).

Una skill es una carpeta con `SKILL.md` (frontmatter YAML con `name` y `description` + instrucciones en Markdown).
Sigue la divulgación progresiva del curso: el nivel 1 es solo el frontmatter, el nivel 2 el cuerpo de `SKILL.md`
y el nivel 3 los archivos de `references/`, `scripts/` y `assets/`, que se leen únicamente bajo demanda.

Una skill explica CÓMO hacer algo y nunca da permisos: no se admite `allowed-tools` y la autorización sigue en
`ToolPolicy`. Adaptaciones fuera del curso: cada skill declara a qué rol de agente sirve (`course-role`), así que la
asigna el código por rol y no un selector léxico; y los niveles 1 y 2 se entregan al agente en su prompt de sistema.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "skills"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    version: str
    role: str | None
    instructions: str


class SkillLoader:
    def __init__(self, root: str | Path = DEFAULT_ROOT):
        self.root = Path(root)
        self.events: list[dict] = []

    def _path(self, name: str) -> Path:
        directory = (self.root / name).resolve()
        if directory.parent != self.root.resolve():
            raise ValueError("La skill debe ser una carpeta directa de la raíz")
        return directory / "SKILL.md"

    @staticmethod
    def _validate(path: Path, front: dict) -> None:
        name, description = front.get("name"), front.get("description")
        if not isinstance(name, str) or not SKILL_NAME.fullmatch(name):
            raise ValueError(f"Nombre de skill inválido: {name!r}")
        if name != path.parent.name:
            raise ValueError("El name del frontmatter debe coincidir con la carpeta")
        if not isinstance(description, str) or not 1 <= len(description) <= 1024:
            raise ValueError("description debe tener entre 1 y 1024 caracteres")
        if "allowed-tools" in front:
            raise ValueError("Una skill no concede permisos: allowed-tools no se admite, la autoridad es ToolPolicy")
        for key, value in (front.get("metadata") or {}).items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("metadata debe ser string → string")

    def _frontmatter(self, path: Path) -> dict:
        """Nivel 1: lee solo el encabezado, sin el cuerpo."""
        lines = []
        with path.open("r", encoding="utf-8") as handle:
            if handle.readline().strip() != "---":
                raise ValueError(f"{path.name} no comienza con frontmatter")
            for line in handle:
                if line.strip() == "---":
                    break
                lines.append(line)
            else:
                raise ValueError(f"{path.name} no cierra el frontmatter")
        front = yaml.safe_load("".join(lines)) or {}
        self._validate(path, front)
        self.events.append({"event": "metadata_read", "skill": front["name"]})
        return front

    def list_summaries(self) -> list[dict]:
        rows = []
        for path in sorted(self.root.glob("*/SKILL.md")):
            front = self._frontmatter(path)
            meta = front.get("metadata") or {}
            rows.append(
                {"name": front["name"], "description": front["description"], "version": meta.get("course-version", "unversioned"), "role": meta.get("course-role")}
            )
        return rows

    def load(self, name: str) -> Skill:
        """Nivel 2: frontmatter + cuerpo completo."""
        path = self._path(name)
        front = self._frontmatter(path)
        _, _, body = path.read_text(encoding="utf-8").split("---", 2)
        if not body.strip():
            raise ValueError("SKILL.md debe contener instrucciones")
        meta = front.get("metadata") or {}
        self.events.append({"event": "skill_body_load", "skill": name})
        return Skill(name, front["description"], meta.get("course-version", "unversioned"), meta.get("course-role"), body.strip())

    def for_role(self, role: str) -> Skill | None:
        for row in self.list_summaries():
            if row["role"] == role:
                return self.load(row["name"])
        return None

    def load_resource(self, name: str, relative_path: str) -> str:
        """Nivel 3, sin poder salir de la carpeta de la skill."""
        directory = self._path(name).parent
        resource = (directory / relative_path).resolve()
        if resource != directory and directory not in resource.parents:
            raise ValueError("Ruta de recurso fuera de la skill")
        if not resource.is_file():
            raise FileNotFoundError(relative_path)
        self.events.append({"event": "resource_load", "skill": name, "resource": relative_path})
        return resource.read_text(encoding="utf-8")


def skill_instructions(role: str, rules_path: Path, loader: SkillLoader | None = None) -> str:
    """Prompt de sistema de un agente: sus reglas (`agent.md`) y, debajo, la skill de su rol."""
    rules = rules_path.read_text(encoding="utf-8")
    skill = (loader or SkillLoader()).for_role(role)
    if skill is None:
        return rules
    return f"{rules}\n\n## Skill del rol: {skill.name} (versión {skill.version})\n{skill.description}\n\n{skill.instructions}"
