# Especificación · Agente Auditor de Proyecto

**Estado:** PROPUESTA (Día 7, sin construir) · **Modelo:** `claude-opus-5-5`, esfuerzo medio · **Código previsto:** `src/backlogguard/agents/auditor/`, `tools/auditor.py`

## Propósito
Comparar lo que se **trató** en las reuniones con lo que se **vendió** en la preventa, detectar cambios de alcance y contradicciones entre reuniones, y custodiar la memoria de decisiones del proyecto. No redacta ítems ni los aprueba.

## Entradas y salidas
- **Entrada:** el tablero (ítems del productor), el índice de fuentes y la memoria del proyecto (`ProjectMemory`).
- **Tools (4):** `comparar_con_preventa` (`read`), `detectar_contradicciones` (`read`), `consultar_decisiones_vigentes` (`read`), `registrar_decision_aprobada` (`local_write`).
- **Salida:** un `AuditReport` validado con Pydantic: lista de hallazgos (`kind`, descripción, ítem afectado opcional, citas y destinatario). La aplicación los convierte en `Finding` del tablero; el Auditor no escribe hallazgos directamente.
- **Pausas:** un hallazgo `cambio_de_alcance` pide decisión del service manager (según `config/policy.yaml`). La pausa en sí la implementa el Día 10; hoy el código solo indica **quién** debe decidir.

## Tipos de hallazgo (ya definidos en el tablero)
`cambio_de_alcance` · `contradiccion` · `tratado_no_vendido` · `vendido_no_tratado` · `decision_evolucionada`

## Requisitos

| ID | Requisito | Test previsto |
|---|---|---|
| AU-01 | `comparar_con_preventa` entrega, por cada punto de la preventa, la evidencia de reuniones e ítems que lo cubren, y por cada tema de reunión si tiene respaldo en la preventa. La clasificación final la hace el modelo. | `test_comparar_preventa_devuelve_evidencia_en_ambos_sentidos` |
| AU-02 | `detectar_contradicciones` agrupa fragmentos de distintas reuniones sobre el mismo tema y los entrega **ordenados por fecha**, con orador y rol. | `test_contradicciones_agrupa_por_tema_y_ordena_por_fecha` |
| AU-03 | Una postura posterior del mismo interlocutor que reemplaza la anterior es `decision_evolucionada`; posturas incompatibles sin esa relación son `contradiccion`. El hallazgo debe incluir ambas citas. | `test_evolucion_vs_contradiccion_en_el_corpus`, `test_hallazgo_exige_citas_verificables` |
| AU-04 | Todo hallazgo lleva al menos una cita; la reunión, fecha y orador salen del fragmento indexado, y la frase se verifica con el mismo chequeo determinístico del Crítico. Un hallazgo con cita falsa se descarta. | `test_hallazgo_con_cita_falsa_se_descarta` |
| AU-05 | `registrar_decision_aprobada` solo escribe si la aplicación entrega una aprobación humana (`approved_by` en el contexto de ejecución, nunca como argumento del modelo). | `test_registrar_decision_exige_aprobacion_humana`, `test_modelo_no_puede_inventar_approved_by` |
| AU-06 | Registrar una decisión que reemplaza a otra la deja como histórica (supersede); `consultar_decisiones_vigentes` devuelve solo las vigentes. | `test_decision_nueva_reemplaza_a_la_vigente` |
| AU-07 | Un hallazgo `cambio_de_alcance` indica que decide el service manager (según la política configurada). | `test_cambio_de_alcance_indica_quien_decide` |
| AU-08 | Solo el Auditor ve sus tools; las de consulta no escriben y solo `registrar_decision_aprobada` es `local_write`. | `test_las_tools_del_auditor_son_solo_del_auditor` |
| AU-09 | El texto de reuniones y preventa es dato no confiable: una orden dentro de un fragmento no se ejecuta. | `test_inyeccion_no_altera_al_auditor` |
| AU-10 | Respeta presupuesto de pasos, tiempo, tools y tokens; si no llega a un informe válido, falla de forma explícita (con una reparación de formato). | `test_auditor_sin_informe_valido_falla` |

## Resultado esperado sobre el corpus sintético (`evals/fixtures/`)
| Hallazgo | Fuente |
|---|---|
| `decision_evolucionada`: reporte mensual PDF → Excel | preventa y kickoff vs. seguimiento |
| `tratado_no_vendido` + `cambio_de_alcance`: app móvil | seguimiento |
| `decision_evolucionada`: filtro por fecha pospuesto | kickoff vs. refinamiento |
| `vendido_no_tratado`: integración con el ERP | preventa (línea a agregar al corpus) |
| `contradiccion`: frecuencia de notificaciones | dos reuniones (línea a agregar al corpus) |

## Fuera del curso (decisiones propias)
- El Auditor no escribe hallazgos; la aplicación los registra (mismo criterio que el Crítico).
- `approved_by` viaja en el contexto de ejecución, igual que `approved_plan_hash`.
- Informe estructurado y verificación determinística de las citas de cada hallazgo.
- Los tipos `decision` y `pregunta_pendiente` de `ProjectMemory` y su fachada (Día 3).

## Límites conocidos (previstos)
- Los embeddings determinísticos agrupan por palabras, no por significado: la agrupación de temas es una ayuda, no un veredicto.
- La clasificación (evolución vs. contradicción) es juicio del modelo; se mide en la evaluación (Día 13).
- Un solo proyecto por corrida.
