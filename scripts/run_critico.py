"""Corre al Crítico sobre ítems sembrados con errores, sin pasar por el productor.

Con LIVE_MODE=0 usa el proveedor falso (solo valida el cableado). Con LIVE_MODE=1 usa el
modelo de config/models.yaml para el rol Crítico (no consume la cuota de Gemini).

    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\run_critico.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from backlogguard.agents.critico import review_item
from backlogguard.board import AgentRole, BacklogItem, Board, Citation
from backlogguard.llm import InvalidProviderResponseError, Settings, build_provider, load_models_config
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary, build_chunks
from backlogguard.tools.critico import check_citations

ROOT = Path(__file__).resolve().parents[1]
GHERKIN = "Dado un cliente con sesión Cuando consulta la función Entonces ve el resultado esperado"


def seed(retriever: InMemoryRetriever) -> Board:
    def cite(document_id: str, query: str, quote: str | None = None) -> Citation:
        chunk = retriever.search(query, top_k=1, filters={"document_id": document_id})[0]
        meta = chunk.metadata
        return Citation(
            fragment_id=chunk.chunk_id,
            quote=quote or chunk.text,
            source_name=meta["source_name"],
            source_type=meta["source_type"],
            source_date=meta["source_date"],
            speaker=meta["speaker"],
        )

    def item(
        item_id: str, title: str, description: str, citation: Citation, *extra: Citation, criteria: list[str] | None = None
    ) -> BacklogItem:
        return BacklogItem(
            id=item_id,
            kind="historia",
            title=title,
            description=description,
            acceptance_criteria=criteria or [GHERKIN],
            citations=[citation, *extra],
        )

    board = Board()
    # 1. Correcta: debería quedar sustentada.
    board.add_item(item("HU-OK", "Notificación por email al cambiar el estado",
                        "Como cliente quiero recibir un email cuando cambia el estado de mi pedido para enterarme al instante.",
                        cite("reunion_01_kickoff", "email nuevo estado"),
                        cite("reunion_03_refinamiento", "notificaciones email menos de un minuto"),
                        criteria=[
                            "Dado un pedido de un cliente Cuando el pedido cambia de estado "
                            "Entonces el cliente recibe un email con el nuevo estado",
                            "Dado un pedido que cambió de estado Cuando pasa un minuto desde el cambio "
                            "Entonces el email ya fue enviado",
                        ]))
    # 2. Cita deformada: la frase no figura textualmente.
    board.add_item(item("HU-CITA", "Filtros por estado y por fecha",
                        "Como cliente quiero filtrar mis pedidos por estado y por fecha para encontrarlos rápido.",
                        cite("reunion_01_kickoff", "listado pedidos filtros",
                             "El cliente puede filtrar sus pedidos por estado, fecha y monto")))
    # 3. Vencida: pide PDF y una reunión posterior lo cambió a Excel.
    board.add_item(item("HU-PDF", "Reporte mensual en PDF",
                        "Como cliente quiero un reporte mensual en PDF para presentarlo en el comité.",
                        cite("reunion_01_kickoff", "reporte mensual PDF")))
    # 4. Duplicadas: dos historias de SSO.
    board.add_item(item("HU-SSO1", "Autenticación mediante SSO corporativo",
                        "Como cliente quiero entrar con el SSO corporativo para no tener usuarios nuevos.",
                        cite("reunion_01_kickoff", "SSO corporativo")))
    board.add_item(item("HU-SSO2", "Autenticación en el portal mediante SSO corporativo",
                        "Como cliente quiero entrar al portal con el SSO corporativo para no crear usuarios.",
                        cite("reunion_01_kickoff", "SSO corporativo")))
    return board


def main() -> int:
    settings = Settings.from_env(ROOT / ".env")
    spec = load_models_config(ROOT / "config" / "models.yaml").for_role(AgentRole.CRITICO)
    provider = build_provider(spec, settings)
    retriever = InMemoryRetriever(DeterministicLexicalEmbeddings())
    library = SourceLibrary(ROOT / "evals" / "fixtures")
    for document_id in library.list_ids():
        document = library.load(document_id)
        retriever.index(build_chunks(document_id, document.text, document.metadata.model_dump(mode="json")))

    board = seed(retriever)
    print(f"modelo={spec.model} effort={spec.effort} live={settings.live_mode}")
    total = 0
    only = set(sys.argv[1:])
    for item_id, item in board.items.items():
        if only and item_id not in only:
            continue
        failed = [c.reason for c in check_citations(item, retriever) if not c.ok]
        try:
            review = review_item(item_id, provider=provider, retriever=retriever, board=board, max_seconds=300.0)
        except InvalidProviderResponseError as exc:
            print(f"- {item_id}: sin veredicto ({exc})")
            continue
        total += review.tokens
        print(f"- {item_id} «{item.title}»: {review.verdict.verdict.upper()} (tokens={review.tokens}) | citas fallidas: {failed or 'ninguna'}")
        for objection in review.verdict.objections:
            print(f"    · {objection}")
    print(f"tokens totales: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
