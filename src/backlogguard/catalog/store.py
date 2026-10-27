"""Catálogo persistente de requisitos en SQLite (fuera del curso).

Es la memoria durable del proyecto: sobrevive a las corridas y solo se vacía con `clear()` (el botón «Empezar proyecto nuevo»).
Reglas que no dependen del modelo:
- La identidad es un número que nunca se reutiliza; el título no es la identidad.
- Una versión nueva exige una propuesta aprobada por una persona: no hay sobreescrituras silenciosas.
- Reprocesar la misma fuente con la misma huella no duplica propuestas ni evidencias.
- La preventa nunca es la única evidencia de un requisito nuevo (lo valida `Proposal`).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from backlogguard.catalog.models import (
    Draft,
    Evidence,
    EvidenceRole,
    Proposal,
    ProposalKind,
    ProposalState,
    Relation,
    Requirement,
    RequirementStatus,
    Version,
)

SourceStatus = Literal["nueva", "procesada", "cambiada"]


class CatalogError(Exception):
    """Operación rechazada por una regla del catálogo."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rid(seq: int) -> str:
    return f"RQ-{seq:03d}"


def _pid(seq: int) -> str:
    return f"P-{seq:03d}"


class Catalog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS requirements (seq INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT NOT NULL, replaced_by TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS versions (requirement_id TEXT NOT NULL, number INTEGER NOT NULL, json TEXT NOT NULL, PRIMARY KEY (requirement_id, number));
                CREATE TABLE IF NOT EXISTS evidences (requirement_id TEXT NOT NULL, number INTEGER NOT NULL, key TEXT NOT NULL, json TEXT NOT NULL, PRIMARY KEY (requirement_id, key));
                CREATE TABLE IF NOT EXISTS proposals (seq INTEGER PRIMARY KEY AUTOINCREMENT, dedupe TEXT NOT NULL UNIQUE, state TEXT NOT NULL, json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources (source_id TEXT NOT NULL, fingerprint TEXT NOT NULL, processed_at TEXT NOT NULL, source_date TEXT, PRIMARY KEY (source_id, fingerprint));
                CREATE TABLE IF NOT EXISTS publications (requirement_id TEXT PRIMARY KEY, version INTEGER NOT NULL, remote_id INTEGER, key TEXT NOT NULL, updated_at TEXT NOT NULL);
                """
            )
            try:  # catálogos creados antes de guardar la fecha de la fuente
                conn.execute("ALTER TABLE sources ADD COLUMN source_date TEXT")
            except sqlite3.OperationalError:
                pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- fuentes procesadas ----

    def source_status(self, source_id: str, fingerprint: str) -> SourceStatus:
        """`procesada` si ya se leyó con esa huella; `cambiada` si se leyó con otra; `nueva` si nunca."""
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT fingerprint FROM sources WHERE source_id = ?", (source_id,)).fetchall()
        if not rows:
            return "nueva"
        return "procesada" if any(r["fingerprint"] == fingerprint for r in rows) else "cambiada"

    def mark_source_processed(self, source_id: str, fingerprint: str, source_date: date | None = None) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR IGNORE INTO sources(source_id, fingerprint, processed_at, source_date) VALUES (?, ?, ?, ?)",
                (source_id, fingerprint, _now(), source_date.isoformat() if source_date else None),
            )

    def latest_processed_date(self, *, exclude: str | None = None) -> date | None:
        """Fecha de la reunión más reciente ya procesada (sin contar `exclude`), para detectar una reunión fuera de orden."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT MAX(source_date) AS latest FROM sources WHERE source_date IS NOT NULL AND source_id != ?", (exclude or "",)
            ).fetchone()
        return date.fromisoformat(row["latest"]) if row and row["latest"] else None

    def processed_sources(self) -> list[dict]:
        with closing(self._connect()) as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM sources ORDER BY processed_at, source_id")]

    # ---- propuestas ----

    def propose(self, proposal: Proposal) -> Proposal:
        """Guarda la propuesta. Idempotente: el mismo candidato de la misma fuente y huella devuelve la ya guardada."""
        dedupe = f"{proposal.source_id}|{proposal.fingerprint}|{proposal.candidate_key}"
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT json FROM proposals WHERE dedupe = ?", (dedupe,)).fetchone()
            if row:
                return Proposal.model_validate_json(row["json"])
            cur = conn.execute("INSERT INTO proposals(dedupe, state, json) VALUES (?, ?, '')", (dedupe, ProposalState.PENDIENTE))
            saved = proposal.model_copy(update={"id": _pid(cur.lastrowid), "created_at": _now(), "state": ProposalState.PENDIENTE})
            conn.execute("UPDATE proposals SET json = ? WHERE seq = ?", (saved.model_dump_json(), cur.lastrowid))
        return saved

    def has_proposal(self, source_id: str, fingerprint: str, candidate_key: str) -> bool:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT 1 FROM proposals WHERE dedupe = ?", (f"{source_id}|{fingerprint}|{candidate_key}",)).fetchone() is not None

    def proposal(self, proposal_id: str) -> Proposal:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT json FROM proposals WHERE seq = ?", (int(proposal_id.split("-")[1]),)).fetchone()
        if not row:
            raise KeyError(f"No existe la propuesta {proposal_id}.")
        return Proposal.model_validate_json(row["json"])

    def proposals(self, *, state: ProposalState | None = None, source_id: str | None = None) -> list[Proposal]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT json FROM proposals ORDER BY seq").fetchall()
        found = [Proposal.model_validate_json(r["json"]) for r in rows]
        return [p for p in found if (state is None or p.state == state) and (source_id is None or p.source_id == source_id)]

    def _save_proposal(self, conn: sqlite3.Connection, proposal: Proposal) -> None:
        conn.execute("UPDATE proposals SET state = ?, json = ? WHERE seq = ?", (proposal.state, proposal.model_dump_json(), int(proposal.id.split("-")[1])))

    def decide(self, proposal_id: str, *, approve: bool, by: str, note: str = "") -> Proposal:
        """Una persona aprueba o rechaza una propuesta pendiente. Aprobar no la aplica: eso lo hace `apply`."""
        if not by.strip():
            raise CatalogError("Una decisión necesita el rol de quien la toma.")
        proposal = self.proposal(proposal_id)
        if proposal.state is not ProposalState.PENDIENTE:
            raise CatalogError(f"{proposal_id} ya está {proposal.state}.")
        decided = proposal.model_copy(update={"state": ProposalState.APROBADA if approve else ProposalState.RECHAZADA, "decided_by": by, "note": note})
        with closing(self._connect()) as conn, conn:
            self._save_proposal(conn, decided)
        return decided

    def edit(self, proposal_id: str, draft: Draft) -> Proposal:
        """Una persona corrige el borrador de una propuesta pendiente antes de decidirla."""
        proposal = self.proposal(proposal_id)
        if proposal.state is not ProposalState.PENDIENTE or not proposal.drafts:
            raise CatalogError(f"{proposal_id} no tiene un borrador pendiente que editar.")
        edited = proposal.model_copy(update={"drafts": [draft, *proposal.drafts[1:]]})
        with closing(self._connect()) as conn, conn:
            self._save_proposal(conn, edited)
        return edited

    def reclassify(self, proposal_id: str, kind: ProposalKind, *, target: str | None = None) -> Proposal:
        """Una persona resuelve un «incierto»: lo convierte en nuevo, refina o cubierto. Queda pendiente y se decide aparte."""
        proposal = self.proposal(proposal_id)
        if proposal.kind is not ProposalKind.INCIERTO or proposal.state is not ProposalState.PENDIENTE:
            raise CatalogError("Solo se reclasifica una propuesta «incierto» pendiente.")
        if kind not in (ProposalKind.NUEVO, ProposalKind.REFINA, ProposalKind.CUBIERTO):
            raise CatalogError("Un incierto solo se resuelve como nuevo, refina o cubierto.")
        if kind is not ProposalKind.NUEVO:
            if not target or self.requirement(target).status is not RequirementStatus.ACTIVO:
                raise CatalogError("Indicá un requisito activo como destino.")
        data = proposal.model_dump()
        data.update(
            kind=kind, targets=[target] if kind is not ProposalKind.NUEVO else [], drafts=[] if kind is ProposalKind.CUBIERTO else data["drafts"][:1],
        )
        resolved = Proposal.model_validate(data)
        with closing(self._connect()) as conn, conn:
            self._save_proposal(conn, resolved)
        return resolved

    def apply_covered(self, proposal_id: str) -> Proposal:
        """«Ya cubierto» solo suma evidencia: no cambia el requisito, por eso no espera una aprobación."""
        proposal = self.proposal(proposal_id)
        if proposal.kind is not ProposalKind.CUBIERTO or proposal.state is not ProposalState.PENDIENTE:
            raise CatalogError("Solo se aplica sin aprobación una propuesta «cubierto» pendiente.")
        return self._apply(proposal, by="automático")

    def apply(self, proposal_id: str) -> Proposal:
        """Aplica una propuesta aprobada: crea o versiona requisitos. Sin aprobación no hace nada."""
        proposal = self.proposal(proposal_id)
        if proposal.state is not ProposalState.APROBADA or not proposal.decided_by:
            raise CatalogError(f"{proposal_id} no está aprobada: no se aplica.")
        return self._apply(proposal, by=proposal.decided_by)

    # ---- aplicar cambios ----

    def _apply(self, proposal: Proposal, *, by: str) -> Proposal:
        with closing(self._connect()) as conn, conn:
            affected: list[str] = []
            kind, drafts, targets = proposal.kind, proposal.drafts, proposal.targets
            for target in targets:
                if self._status(conn, target) is not RequirementStatus.ACTIVO:
                    raise CatalogError(f"{target} no está activo: no se puede cambiar.")
            if kind is ProposalKind.NUEVO:
                affected = [self._create(conn, drafts[0], Relation.NUEVO, [], proposal, by)]
            elif kind is ProposalKind.REFINA:
                affected = [self._new_version(conn, targets[0], drafts[0], Relation.REFINA, proposal, by)]
            elif kind is ProposalKind.CUBIERTO:
                self._evidence(conn, targets[0], self._current_number(conn, targets[0]), proposal.evidence, EvidenceRole.REFUERZO)
                affected = [targets[0]]
            elif kind is ProposalKind.CONTRADICE:
                if drafts:
                    affected = [self._new_version(conn, targets[0], drafts[0], Relation.REEMPLAZA, proposal, by)]
                else:
                    self._evidence(conn, targets[0], self._current_number(conn, targets[0]), proposal.evidence, EvidenceRole.CONTRADICE)
                    affected = [targets[0]]
            elif kind is ProposalKind.DIVIDE:
                children = [self._create(conn, d, Relation.DIVIDE, targets, proposal, by) for d in drafts]
                self._set_status(conn, targets[0], RequirementStatus.DIVIDIDO, children)
                affected = [targets[0], *children]
            elif kind is ProposalKind.FUSIONA:
                merged = self._create(conn, drafts[0], Relation.FUSIONA, targets, proposal, by)
                for target in targets:
                    self._set_status(conn, target, RequirementStatus.FUSIONADO, [merged])
                affected = [*targets, merged]
            done = proposal.model_copy(update={"state": ProposalState.APLICADA, "decided_by": proposal.decided_by or by, "affected": affected})
            self._save_proposal(conn, done)
        return done

    def _status(self, conn: sqlite3.Connection, rid: str) -> RequirementStatus:
        row = conn.execute("SELECT status FROM requirements WHERE seq = ?", (int(rid.split("-")[1]),)).fetchone()
        if not row:
            raise KeyError(f"No existe el requisito {rid}.")
        return RequirementStatus(row["status"])

    def _set_status(self, conn: sqlite3.Connection, rid: str, status: RequirementStatus, replaced_by: list[str]) -> None:
        conn.execute("UPDATE requirements SET status = ?, replaced_by = ? WHERE seq = ?", (status, json.dumps(replaced_by), int(rid.split("-")[1])))

    def _current_number(self, conn: sqlite3.Connection, rid: str) -> int:
        return conn.execute("SELECT MAX(number) FROM versions WHERE requirement_id = ?", (rid,)).fetchone()[0]

    def _create(self, conn: sqlite3.Connection, draft: Draft, relation: Relation, parents: list[str], proposal: Proposal, by: str) -> str:
        cur = conn.execute("INSERT INTO requirements(status) VALUES (?)", (RequirementStatus.ACTIVO,))
        rid = _rid(cur.lastrowid)
        self._write_version(conn, rid, 1, draft, relation, parents, proposal, by)
        return rid

    def _new_version(self, conn: sqlite3.Connection, rid: str, draft: Draft, relation: Relation, proposal: Proposal, by: str) -> str:
        self._write_version(conn, rid, self._current_number(conn, rid) + 1, draft, relation, [], proposal, by)
        return rid

    def _write_version(self, conn, rid, number, draft, relation, parents, proposal, by) -> None:
        version = Version(requirement_id=rid, number=number, relation=relation, draft=draft, parents=parents, proposal_id=proposal.id or None, approved_by=by, created_at=_now())
        conn.execute("INSERT INTO versions VALUES (?, ?, ?)", (rid, number, version.model_dump_json()))
        self._evidence(conn, rid, number, proposal.evidence, EvidenceRole.ORIGEN)

    def _evidence(self, conn: sqlite3.Connection, rid: str, number: int, items: list[Evidence], role: EvidenceRole) -> None:
        for item in items:
            item = item.model_copy(update={"role": role if item.role is EvidenceRole.ORIGEN else item.role})
            conn.execute("INSERT OR IGNORE INTO evidences VALUES (?, ?, ?, ?)", (rid, number, item.key, item.model_dump_json()))

    # ---- lectura ----

    def requirement(self, rid: str) -> Requirement:
        with closing(self._connect()) as conn:
            head = conn.execute("SELECT * FROM requirements WHERE seq = ?", (int(rid.split("-")[1]),)).fetchone()
            if not head:
                raise KeyError(f"No existe el requisito {rid}.")
            versions = [Version.model_validate_json(r["json"]) for r in conn.execute("SELECT json FROM versions WHERE requirement_id = ? ORDER BY number", (rid,))]
            evidences = [(r["number"], Evidence.model_validate_json(r["json"])) for r in conn.execute("SELECT number, json FROM evidences WHERE requirement_id = ?", (rid,))]
        last = versions[-1].number
        for version in versions:
            version.current = version.number == last
            version.evidence = [e for n, e in evidences if n == version.number and e.role is not EvidenceRole.CONTRADICE]
        # el refuerzo se anota sobre la versión vigente en el momento; para leerlo se junta todo lo que no contradice
        versions[-1].evidence = [e for _, e in evidences if e.role is not EvidenceRole.CONTRADICE]
        conflicts = [e for _, e in evidences if e.role is EvidenceRole.CONTRADICE]
        return Requirement(id=rid, status=RequirementStatus(head["status"]), replaced_by=json.loads(head["replaced_by"]), current=versions[-1], versions=versions, conflicts=conflicts)

    def requirements(self, status: RequirementStatus | None = None) -> list[Requirement]:
        with closing(self._connect()) as conn:
            seqs = [r["seq"] for r in conn.execute("SELECT seq FROM requirements ORDER BY seq")]
        found = [self.requirement(_rid(s)) for s in seqs]
        return [r for r in found if status is None or r.status is status]

    # ---- publicación ----

    def publication_key(self, rid: str, version: int | None = None) -> str:
        """Clave de idempotencia por requisito y versión: la misma versión no se publica dos veces."""
        number = version or self.requirement(rid).current.number
        return hashlib.sha256(f"{rid}:v{number}".encode()).hexdigest()[:16]

    def to_publish(self) -> list[Requirement]:
        """Requisitos activos que nunca se publicaron o cuya versión vigente es más nueva que la publicada."""
        found = []
        for requirement in self.requirements(RequirementStatus.ACTIVO):
            published = self.publication(requirement.id)
            if published is None or published["needs_update"]:
                found.append(requirement)
        return found

    def mark_published(self, rid: str, remote_id: int, version: int | None = None) -> None:
        """Anota lo publicado. `version` es la que se publicó: puede ser anterior a la vigente si se aprobó otra mientras tanto."""
        number = version or self.requirement(rid).current.number
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO publications VALUES (?, ?, ?, ?, ?) ON CONFLICT(requirement_id) DO UPDATE SET version = excluded.version, "
                "remote_id = excluded.remote_id, key = excluded.key, updated_at = excluded.updated_at",
                (rid, number, remote_id, self.publication_key(rid, number), _now()),
            )

    def publication(self, rid: str) -> dict | None:
        """Qué se publicó del requisito y si hay que actualizarlo (la versión vigente es más nueva que la publicada)."""
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM publications WHERE requirement_id = ?", (rid,)).fetchone()
        if not row:
            return None
        return {**dict(row), "needs_update": row["version"] < self.requirement(rid).current.number}

    # ---- proyecto nuevo ----

    def clear(self) -> None:
        """Vacía todo el catálogo. Solo lo llama «Empezar proyecto nuevo», con confirmación."""
        with closing(self._connect()) as conn, conn:
            for table in ("requirements", "versions", "evidences", "proposals", "sources", "publications"):
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM sqlite_sequence")
