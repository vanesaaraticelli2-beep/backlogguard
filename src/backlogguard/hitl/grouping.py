"""Agrupa los hallazgos de un mismo asunto en un único pedido de decisión.

Dos hallazgos son del mismo asunto si comparten al menos una cita (el mismo fragmento de una fuente).
Así "tratado y no vendido" y "cambio de alcance" sobre la app móvil se deciden una sola vez.
Fuera del curso.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from backlogguard.board import AgentRole, Finding, FindingKind
from backlogguard.hitl.models import Evidence

# Qué condición de `config/policy.yaml` decide cada tipo de hallazgo, y cuál prima si un grupo mezcla razones.
REASON_BY_KIND = {
    FindingKind.CAMBIO_DE_ALCANCE: "cambio_de_alcance",
    FindingKind.TRATADO_NO_VENDIDO: "cambio_de_alcance",
    FindingKind.VENDIDO_NO_TRATADO: "vendido_no_tratado",
    FindingKind.CONTRADICCION: "contradiccion",
}
REASON_PRIORITY = ("cambio_de_alcance", "vendido_no_tratado", "contradiccion")
MAX_EVIDENCE = 6


@dataclass
class FindingGroup:
    findings: list[Finding] = field(default_factory=list)

    @property
    def fragment_ids(self) -> list[str]:
        return sorted({c.fragment_id for f in self.findings for c in f.citations})

    @property
    def group_id(self) -> str:
        return "G-" + hashlib.sha1("|".join(sorted(f.id for f in self.findings)).encode()).hexdigest()[:8]

    @property
    def topic_key(self) -> str:
        """Clave estable del asunto (depende de las fuentes, no de cómo se redacte el hallazgo)."""
        return "alcance-" + hashlib.sha1("|".join(self.fragment_ids).encode()).hexdigest()[:10]

    @property
    def reason(self) -> str | None:
        reasons = {REASON_BY_KIND[f.kind] for f in self.findings if f.kind in REASON_BY_KIND}
        return next((r for r in REASON_PRIORITY if r in reasons), None)

    @property
    def summary(self) -> str:
        return "\n".join(f"- {f.description}" for f in self.findings)

    def evidence(self) -> list[Evidence]:
        seen: set[str] = set()
        result: list[Evidence] = []
        for finding in self.findings:
            for citation in finding.citations:
                if citation.fragment_id in seen:
                    continue
                seen.add(citation.fragment_id)
                result.append(
                    Evidence(
                        fragment_id=citation.fragment_id,
                        quote=citation.quote,
                        source_name=citation.source_name,
                        source_date=citation.source_date.isoformat(),
                        speaker=citation.speaker,
                    )
                )
        return result[:MAX_EVIDENCE]


def group_findings(findings: list[Finding]) -> list[FindingGroup]:
    """Grupos de hallazgos dirigidos al Supervisor que comparten citas y piden una decisión humana."""
    candidates = [f for f in findings if f.addressee is AgentRole.SUPERVISOR]
    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    owner: dict[str, int] = {}
    for index, finding in enumerate(candidates):
        for citation in finding.citations:
            if citation.fragment_id in owner:
                parent[find(index)] = find(owner[citation.fragment_id])
            else:
                owner[citation.fragment_id] = index

    buckets: dict[int, FindingGroup] = {}
    for index, finding in enumerate(candidates):
        buckets.setdefault(find(index), FindingGroup()).findings.append(finding)
    return [group for group in buckets.values() if group.reason is not None]
