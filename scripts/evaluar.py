"""Evaluación: mide qué tan bien trabaja el sistema contra respuestas conocidas y lo compara con un agente único.

Tres pasos, todos con las mismas respuestas esperadas (`evals/dataset/acme.json` o las tuyas en `evals/real/`):

1. Correr el sistema (por la pantalla o con scripts/correr_con_mis_fuentes.py) y puntuar la corrida guardada:
       .venv\\Scripts\\python scripts\\evaluar.py puntuar --nombre completo --datos data
   Para la ablación, correr antes con BACKLOGGUARD_ABLATE=critico, auditor o critico,auditor
   y puntuar con --nombre sin_critico, sin_auditor, etc.
2. El agente único (una sola llamada a un modelo real, gasta tokens):
       $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\evaluar.py agente-unico
3. La tabla comparativa:
       .venv\\Scripts\\python scripts\\evaluar.py tabla

Los resultados quedan en `evals/resultados/<caso>/<variante>.json`. Puntuar y armar la tabla no gastan nada.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backlogguard.board import AgentRole
from backlogguard.evaluation import cargar_verdad, puntuar
from backlogguard.evaluation.baseline import correr_agente_unico
from backlogguard.evaluation.outputs import fuentes_de, salida_desde_catalogo, salida_desde_estado
from backlogguard.evaluation.report import tabla_markdown
from backlogguard.graph import load_state
from backlogguard.graph.setup import build_run_deps, open_graph
from backlogguard.llm import Settings, load_models_config
from backlogguard.llm.providers import build_provider
from backlogguard.rag import SourceLibrary

ROOT = Path(__file__).resolve().parents[1]
VERDAD = ROOT / "evals" / "dataset" / "acme.json"
FUENTES = ROOT / "evals" / "fixtures"


def guardar(resultado: dict, carpeta: Path | None) -> Path:
    carpeta = carpeta or ROOT / "evals" / "resultados" / resultado["caso"].split()[0].casefold()
    carpeta.mkdir(parents=True, exist_ok=True)
    path = carpeta / f"{resultado['variante']}.json"
    path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def mostrar(resultado: dict) -> None:
    print(tabla_markdown([resultado]))
    for clave, titulo in (("requisitos", "Requisitos"), ("hallazgos", "Hallazgos")):
        faltan = resultado[clave].get("faltantes") or resultado[clave].get("no_detectados")
        print(f"{titulo} que faltan: {faltan or 'ninguno'}")
    print(f"Requisitos inventados: {resultado['requisitos']['inventados'] or 'ninguno'}")
    print(f"Falsas alarmas: {resultado['hallazgos']['falsas_alarmas'] or 'ninguna'}")
    print(f"Citas no verificables: {resultado['citas']['no_verificables'] or 'ninguna'}")
    if resultado["errores"]:
        print(f"Errores de la corrida: {resultado['errores']}")


def puntuar_corrida(options) -> int:
    settings = Settings.from_env(ROOT / ".env")
    data = Path(options.datos).resolve()
    library_dir = Path(options.fuentes) if options.fuentes else (data / "fuentes" if (data / "fuentes").is_dir() else FUENTES)
    deps = build_run_deps(ROOT, settings, data_dir=data, sources_dir=library_dir)
    graph = open_graph(deps, data)
    thread_id = options.corrida or _ultima(graph)
    if thread_id is None:
        print(f"No hay corridas guardadas en {data}.")
        return 1
    state = load_state(graph, thread_id)
    print(f"Corrida {thread_id}: estado={state.get('status')} tokens={state.get('tokens', 0):,}")
    verdad = cargar_verdad(options.verdad)
    if options.desde == "auto":
        salida = salida_desde_estado(options.nombre, state, deps.catalog)
    else:  # flujo con documentos propios: lo que propusieron los agentes, o lo que quedó aprobado
        salida = salida_desde_catalogo(options.nombre, deps.catalog, state, propuestas=options.desde == "propuestas")
    resultado = puntuar(verdad, salida, fuentes_de(SourceLibrary(library_dir)))
    mostrar(resultado)
    print(f"\nGuardado en {guardar(resultado, Path(options.salida) if options.salida else None)}")
    return 0


def _ultima(graph) -> str | None:
    conn = graph.checkpointer.conn
    row = conn.execute("SELECT thread_id FROM checkpoints GROUP BY thread_id ORDER BY MAX(checkpoint_id) DESC LIMIT 1").fetchone()
    return row[0] if row else None


def agente_unico(options) -> int:
    settings = Settings.from_env(ROOT / ".env")
    if not settings.live_mode:
        print("El agente único se mide con un modelo real: hace falta LIVE_MODE=1 (gasta tokens).")
        return 1
    spec = load_models_config(ROOT / "config" / "models.yaml").for_role(AgentRole.REQUERIMIENTOS)  # el mismo modelo del productor
    library = SourceLibrary(Path(options.fuentes) if options.fuentes else FUENTES)
    salida = correr_agente_unico(build_provider(spec, settings), library, options.nombre)
    resultado = puntuar(cargar_verdad(options.verdad), salida, fuentes_de(library))
    mostrar(resultado)
    print(f"\nGuardado en {guardar(resultado, Path(options.salida) if options.salida else None)}")
    return 0


def tabla(options) -> int:
    carpeta = Path(options.carpeta) if options.carpeta else ROOT / "evals" / "resultados" / "acme"
    resultados = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(carpeta.glob("*.json"))]
    if not resultados:
        print(f"No hay resultados en {carpeta}.")
        return 1
    print(tabla_markdown(resultados))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    for name in ("puntuar", "agente-unico"):
        p = sub.add_parser(name)
        p.add_argument("--nombre", default="completo" if name == "puntuar" else "agente_unico")
        p.add_argument("--verdad", default=str(VERDAD), help="respuestas esperadas (JSON)")
        p.add_argument("--fuentes", help="carpeta con las fuentes; por defecto data/fuentes si existe y, si no, evals/fixtures")
        p.add_argument("--salida", help="carpeta donde guardar el resultado")
        if name == "puntuar":
            p.add_argument("--datos", default=str(ROOT / "data"), help="carpeta de datos de la corrida (corridas.sqlite y catalogo.sqlite)")
            p.add_argument("--corrida", help="thread_id; por defecto, la más reciente")
            p.add_argument("--desde", choices=["auto", "propuestas", "catalogo"], default="auto",
                           help="auto: como antes; propuestas: lo que propusieron los agentes al leer las reuniones; catalogo: lo aprobado")
    t = sub.add_parser("tabla")
    t.add_argument("--carpeta")
    options = parser.parse_args()
    return {"puntuar": puntuar_corrida, "agente-unico": agente_unico, "tabla": tabla}[options.comando](options)


if __name__ == "__main__":
    sys.exit(main())
