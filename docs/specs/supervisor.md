# Especificación · Supervisor y grafo de la corrida

**Estado:** implementado (Día 8) · **Modelo del Supervisor:** `claude-sonnet-5-5`, esfuerzo bajo · **Código:** `src/backlogguard/graph/`, `agents/supervisor/`, `tools/supervisor.py`, `config/budgets.yaml`

## Propósito
Coordinar a los agentes en una corrida completa: de las fuentes al tablero revisado, auditado y con las decisiones humanas identificadas. El Supervisor planifica, delega y escala; **no redacta ni escribe en el tablero**. La pausa real para que una persona decida (`interrupt`) es del Día 10; hoy la corrida termina en `esperando_decision` con las escalaciones registradas.

## Diseño: qué decide el modelo y qué decide el código
| Decide el modelo (Supervisor) | Decide el código |
|---|---|
| Qué fuentes de la biblioteca usar y qué instrucción darle al productor. | El orden de los pasos y que Crítico y Auditor **siempre** participen. |
| El resumen final para las personas. | Cuándo se escala y a quién (según `config/policy.yaml`). |
| | Los topes: 2 rondas, una sola reapertura tras la auditoría, presupuestos. |

## Grafo (LangGraph, patrón de la clase 11)
`plan → producir → revisar (uno por ítem, en bucle) → auditar → [si hubo ítems reabiertos y es la primera vez: revisar] → escalar → resumir → fin`

- Estado: `TypedDict` serializable; el tablero viaja como JSON.
- Persistencia: `SqliteSaver` por `thread_id` (la clase 11 lo usa igual).
- Tools del Supervisor: `delegar_tarea` y `escalar_a_persona` (ambas `compute`; registran, no ejecutan).

## Requisitos

| ID | Requisito | Test que lo verifica |
|---|---|---|
| SU-01 | El Supervisor ve solo `delegar_tarea` y `escalar_a_persona`; ningún otro rol las ve y ninguna escribe en el tablero. | `test_las_tools_del_supervisor_son_solo_del_supervisor` |
| SU-02 | `delegar_tarea` valida el agente destino, el tipo de tarea y que las fuentes existan en la biblioteca; hay un máximo de delegaciones. | `test_delegar_valida_agente_tarea_y_fuentes` |
| SU-03 | `escalar_a_persona` toma de la política quién decide; el modelo no lo elige. Las razones son un conjunto cerrado y no se duplican. | `test_escalar_usa_la_politica_y_no_duplica` |
| SU-04 | El plan del Supervisor solo elige fuentes e instrucciones: si omite al Crítico o al Auditor, el grafo igual los ejecuta. Un plan inválido o vacío cae al plan por defecto. | `test_el_plan_no_puede_saltarse_al_critico_ni_al_auditor`, `test_plan_invalido_cae_al_plan_por_defecto` |
| SU-05 | La corrida respeta el orden fijo del grafo. | `test_corrida_feliz_recorre_el_grafo_en_orden` |
| SU-06 | Cada ítem se revisa por separado con `negotiate_item` (máximo 2 rondas) y el estado se guarda tras cada ítem. | `test_revision_por_item_con_checkpoint`, `test_objecion_correccion_y_acuerdo_dentro_de_la_corrida` |
| SU-07 | Tras la auditoría, los ítems reabiertos vuelven a revisión **una sola vez**; no hay ciclos. | `test_la_auditoria_reabre_una_sola_vez` |
| SU-08 | Se escala por código: `sin_consenso` y `contradiccion` → PO; `cambio_de_alcance`, `tratado_no_vendido` y `vendido_no_tratado` → service manager. | `test_escalaciones_obligatorias_por_codigo_y_sin_consenso` |
| SU-09 | Los presupuestos por corrida (tokens, ítems a revisar, tiempo) cortan la corrida con estado `presupuesto_agotado`; lo que no se revisó queda pendiente. | `test_presupuesto_agotado_corta_la_corrida`, `test_presupuesto_de_items_deja_pendiente_lo_que_no_se_reviso`, `test_el_presupuesto_se_carga_y_valida` |
| SU-10 | El estado se guarda en SQLite por `thread_id` y una segunda instancia del grafo lo lee tal cual. | `test_el_estado_se_persiste_y_otra_instancia_lo_lee` |
| SU-11 | Al final, cada ítem tiene estado y cada escalación referencia un ítem o un hallazgo. | `test_el_resultado_final_es_trazable` |
| SU-12 | Un error de un agente (modelo caído, veredicto inválido) queda registrado y no tumba la corrida: el ítem afectado queda marcado y se sigue con los demás. La corrida termina `completada_con_errores` si no hay escalaciones. | `test_un_error_de_agente_no_tumba_la_corrida` |
| SU-13 | El texto de las fuentes no cambia el plan ni las escalaciones: una orden dentro de una reunión no altera el recorrido. | `test_inyeccion_no_altera_el_recorrido` |

## Estados finales de una corrida
`completada` · `esperando_decision` (hay escalaciones) · `completada_con_errores` · `presupuesto_agotado`

## Fuera del curso (decisiones propias)
- Supervisor acotado: el modelo elige fuentes e instrucciones y redacta el resumen; el recorrido y las escalaciones son reglas.
- `config/budgets.yaml` validado con Pydantic, como `models.yaml` y `policy.yaml`.
- El tablero viaja como JSON dentro del estado del grafo; el índice de fuentes se reconstruye al reanudar.
- Dependencias nuevas: `langgraph` y `langgraph-checkpoint-sqlite` (la clase 11 usa ambas).

## Límites conocidos
- Sin `interrupt` todavía: la corrida termina esperando la decisión (Día 10).
- Sin Integración (Día 9): la corrida no publica.
- Una corrida procesa un proyecto y los ítems en secuencia, no en paralelo.
- La plantilla de redacción solo admite reuniones y minutas: el código quita la preventa de las fuentes del productor, aunque el Supervisor la elija.
- El índice de fuentes se reconstruye al compilar el grafo; con Qdrant persistente (a evaluar) no haría falta.
