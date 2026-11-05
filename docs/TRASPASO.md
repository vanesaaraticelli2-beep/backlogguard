# Traspaso: datos del proyecto real (LogiCorp · DMS Elecciones)

Estado al 2026-11-05. Este repositorio trae el código, el material del curso y **todos los datos de trabajo** del caso real, anonimizado: la preventa, las tres minutas, la línea base, el catálogo de requisitos y las corridas guardadas.

## Qué hay y dónde

| Carpeta | Qué contiene |
|---|---|
| `data_real/fuentes/` | Preventa y minutas del 24-08, 25-08 y 27-08, **ya anonimizadas y limpias** (como las lee el sistema). |
| `data_real/linea_base/` | Los 334 compromisos extraídos de la preventa (incluido, condición, excluido) con su cita y página. |
| `data_real/catalogo.sqlite` | Catálogo de requisitos: 33 requisitos activos y las 62 propuestas de las tres lecturas, con lo que se aprobó o rechazó. |
| `data_real/corridas.sqlite` | Las corridas de los agentes (checkpoints de LangGraph). La buena es `corrida-c398d612`. |
| `data_real/publicaciones.sqlite`, `memoria.sqlite` | Registro de publicaciones y memoria del proyecto. |
| `data_real_copia_antes_de_gastar/` | Copias de seguridad del catálogo en etapas anteriores (antes de reabrir, antes de borrar lecturas, con el 24-08 aprobado). |
| `data/` | El caso de demostración (portal de venta de seguros) con su corrida grabada. |
| `evals/real/` | Respuestas esperadas anonimizadas (`*.anonimo.md`), auditoría de vínculos y la línea base incompleta del primer intento. |
| `Curso ITBA/` | Las notebooks de las clases 1 a 13 del curso. |

## Cómo abrirlo

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev,llm,rag,graph,ui]"   # en Linux/Mac: .venv/bin/pip
cp .env.example .env                                     # y poné tu ANTHROPIC_API_KEY y LIVE_MODE=1
BACKLOGGUARD_DATA=data_real streamlit run src/backlogguard/ui/app.py --server.port 8502
```

Sin `BACKLOGGUARD_DATA` la pantalla abre `data/` (la demo). Con `LIVE_MODE=0` no se llama a ningún modelo.

## En qué estado quedó

- **Las tres minutas están leídas y decididas** en «Revisión» (33 requisitos activos).
- **`corrida-c398d612`**: 33 historias redactadas en 9 tandas y revisadas por el Crítico. Las 9 sin consenso las aprobó el product owner. El **plan de publicación (versión 2: 33 a crear, 0 omitidos) quedó pendiente a propósito**: todavía no se publica en Azure DevOps.
- Para volver a ella: pestaña «Corrida» → corridas guardadas → `corrida-c398d612` → **«Retomar y decidir lo pendiente»**. No uses «Iniciar corrida»: arranca una corrida nueva y gasta modelos (la completa costó unos US$7).
- `corrida-1a8cd2ef`, `corrida-54eb4db6` y `corrida-b0affae5` son corridas viejas o interrumpidas. Se pueden ignorar o borrar.

## Lo que NO está en el repositorio (se pide por otro canal)

El repositorio es público, así que no se suben documentos que identifican al cliente o a las personas:

- `entrada/`: los PDF originales de las preventas, sin anonimizar.
- `evals/real/anonimizacion.yaml`: el diccionario que revierte el anonimato.
- Las versiones no anónimas de `evals/real/` (`esperados_cruces_preventa_minutas.md`, `esperados_minuta_2026-08-24.md`, `limpieza_preventa_andreani.md`).
- `.env`: las claves de API. Cada uno usa la suya.

Para trabajar con los datos anonimizados no hacen falta. Solo sirven para volver a importar las fuentes desde cero.

## Mejoras recientes que todavía no se probaron con modelos reales

Están en el código y en los tests, pero no se midieron en una corrida real:

- Al redactar, la historia hereda el **fragmento completo** de la minuta y no solo la frase corta.
- El Crítico, en la segunda ronda, solo verifica lo que objetó.
- El productor tiene una lista de control con lo que el Crítico objeta primero.

En la corrida anterior el Crítico objetó 28 de 33 historias en la primera ronda. Conviene medirlo con una corrida chica, de 6 a 8 requisitos, antes de repetir la completa.
