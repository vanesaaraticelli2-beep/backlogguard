"""Compara corridas guardadas: objeciones del Crítico en la 1ª ronda, desacuerdos sin consenso, tokens y costo por historia.

No gasta nada: lee las corridas de `<datos>/corridas.sqlite`.

    .venv\\Scripts\\python scripts\\comparar_corridas.py --datos data_real corrida-c398d612 corrida-xxxxxxxx
    .venv\\Scripts\\python scripts\\comparar_corridas.py --datos data_real --requisitos RQ-003,RQ-004 corrida-c398d612 corrida-xxxxxxxx
    .venv\\Scripts\\python scripts\\comparar_corridas.py --datos data_real --listar
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from backlogguard.evaluation.corridas import metrics, table
from backlogguard.llm.metering import load_pricing


def states(path: Path) -> dict[str, dict]:
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)) as conn:
        saver = SqliteSaver(conn)
        ids = [row[0] for row in conn.execute("SELECT thread_id FROM checkpoints GROUP BY thread_id ORDER BY MAX(checkpoint_id)")]
        return {tid: saver.get_tuple({"configurable": {"thread_id": tid}}).checkpoint["channel_values"] for tid in ids}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corridas", nargs="*", help="ids de las corridas a comparar (corrida-xxxxxxxx)")
    parser.add_argument("--datos", default="data", help="carpeta de datos (data o data_real)")
    parser.add_argument("--requisitos", default="", help="comparar solo las historias de estos requisitos (RQ-003,RQ-004,…)")
    parser.add_argument("--listar", action="store_true", help="mostrar las corridas guardadas")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    saved = states(Path(args.datos) / "corridas.sqlite")
    if args.listar or not args.corridas:
        for tid, state in saved.items():
            print(f"{tid}  {state.get('status', '?'):30} historias={len((state.get('board') or {}).get('items', {}))}  tokens={state.get('tokens', 0):,}")
        return 0
    unknown = [c for c in args.corridas if c not in saved]
    if unknown:
        print("No existen: " + ", ".join(unknown), file=sys.stderr)
        return 1
    wanted = {r.strip().upper() for r in args.requisitos.split(",") if r.strip()} or None
    pricing = load_pricing()
    print(table([metrics(c, saved[c], pricing, wanted) for c in args.corridas]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
