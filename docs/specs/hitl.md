# Especificación · Human-in-the-Loop y pantalla de decisiones

**Estado:** implementado (Día 10, etapas 10a y 10b) · **Código:** `src/backlogguard/hitl/`, `graph/` (nodos con `interrupt`), `config/people.yaml`, `ui/` (Streamlit), `llm/recording.py`, `scripts/decidir.py`, `scripts/grabar_demo.py`

## Propósito
Que el sistema se detenga y espere a la persona correcta en los momentos que importan, que su decisión quede ligada a la versión exacta que vio y que la corrida continúe desde donde quedó, incluso desde otro proceso. Cierra el recorrido: tras la decisión humana, lo aprobado se publica en el backlog simulado.

## Qué se decide y quién decide
| Qué espera una decisión | Quién decide (`config/policy.yaml`) | Qué pasa con cada acción |
|---|---|---|
| **Cambio de alcance** (incluye "tratado y no vendido") | service manager | Aprobar o rechazar el cambio queda registrado como decisión del proyecto; editar corrige el texto antes de registrarla. |
| **Vendido y no tratado** | service manager | Igual: se registra si se mantiene o se descarta. |
| **Contradicción entre reuniones** | product owner | Se registra qué postura prevalece (aprobar, rechazar o editar el texto). |
| **Desacuerdo sin consenso** tras 2 rondas | product owner | Aprobar: el ítem pasa a sustentado. Rechazar: se excluye. Editar: se corrige el ítem y pasa a sustentado. |
| **Plan de publicación** | full stack IA engineer | Aprobar: los ítems pasan a aprobados y se publica. Editar: se excluyen ítems y el plan nuevo requiere otra aprobación. Rechazar: no se publica nada. |

## Contrato de una decisión (clase 11)
- `DecisionRequest`: id, tipo, razón, quién decide, resumen, evidencia (citas), campos editables, **versión** y **hash** del contenido.
- `HumanDecision`: acción (`approve`, `edit`, `reject`), persona, rol, id, **versión** y **hash** de lo que vio, datos editados y comentario.
- Una edición **crea una versión nueva** que debe aprobarse otra vez; nunca hereda la aprobación.

## Recorrido del grafo (cambios sobre el Día 9)
`… → auditar → escalar (agrupado) → **decidir** (pausa, una por pedido) → armar el plan → **aprobar el plan** (pausa) → publicar → resumir`

Los desacuerdos sobre ítems se resuelven **antes** de armar el plan, para que un ítem aprobado por el PO pueda entrar.

## Requisitos

| ID | Requisito | Test que lo verifica |
|---|---|---|
| HI-01 | Los hallazgos que comparten citas se agrupan en un único pedido de decisión; si el grupo mezcla razones, prima la del service manager. Un mismo asunto no genera dos pedidos. | `test_los_hallazgos_del_mismo_asunto_se_agrupan`, `test_la_razon_del_service_manager_prima_en_un_grupo`, `test_cada_asunto_pide_una_sola_decision_a_quien_corresponde` |
| HI-02 | Cada pedido tiene versión y hash; una decisión con otra versión, otro hash u otro id se rechaza y no cambia nada. | `test_el_hash_del_pedido_cubre_su_contenido`, `test_una_decision_vieja_o_adulterada_se_rechaza` |
| HI-03 | Solo decide quien tiene el rol que fija la política; cualquier otro rol es rechazado. | `test_solo_decide_el_rol_que_corresponde`, `test_el_archivo_de_personas_cubre_a_quienes_deciden_segun_la_politica` |
| HI-04 | La corrida se pausa con `interrupt`, el estado queda en SQLite y otra instancia del grafo la retoma con la decisión (`Command(resume=...)`). | `test_la_corrida_se_pausa_y_se_retoma_desde_otra_instancia` |
| HI-05 | Antes de cada pausa no hay efectos; los efectos posteriores son idempotentes, así que reanudar dos veces no duplica nada. | `test_reanudar_dos_veces_no_duplica_efectos` |
| HI-06 | Desacuerdo sin consenso: aprobar → sustentado; rechazar → excluido; editar → ítem corregido, nueva versión del pedido y luego sustentado. | `test_el_po_resuelve_un_desacuerdo_aprobando_editando_o_rechazando` |
| HI-07 | Cambio de alcance, vendido sin tratar y contradicción: la decisión se registra en la memoria del proyecto con quién la aprobó; una corrida posterior no la vuelve a plantear. | `test_la_decision_queda_en_la_memoria_con_su_aprobador`, `test_una_decision_vigente_no_se_vuelve_a_escalar` |
| HI-08 | Editar crea la versión 2 del pedido; la aprobación de la versión 1 no sirve para la 2. | `test_editar_crea_una_version_nueva_que_hay_que_aprobar`, `test_editar_el_texto_de_una_decision_exige_aprobar_la_version_nueva`, `test_solo_se_edita_lo_editable_y_con_datos_validos` |
| HI-09 | Los desacuerdos de ítems se resuelven antes de armar el plan; un ítem aprobado por el PO entra al plan. | `test_un_item_aprobado_por_el_po_entra_al_plan` |
| HI-10 | Plan: aprobar publica; editar (excluir ítems) genera otro plan con otro hash que exige nueva aprobación; rechazar no publica. | `test_aprobar_el_plan_publica`, `test_excluir_items_genera_un_plan_nuevo`, `test_no_se_puede_excluir_lo_que_no_esta_en_el_plan`, `test_rechazar_el_plan_no_publica` |
| HI-11 | Se publica solo el plan cuyo hash se aprobó; si el backlog cambió entre la aprobación y la ejecución, no se publica. | `test_un_cambio_del_backlog_tras_aprobar_bloquea_la_publicacion` |
| HI-12 | Cada decisión deja registro: persona, rol, momento, acción, versión, hash y comentario. | `test_cada_decision_queda_auditada` |
| HI-13 | Rechazarlo todo termina en un estado final válido, sin errores. | `test_rechazarlo_todo_termina_bien`, `test_el_recorrido_completo_con_todas_las_decisiones` |
| HI-14 | Una decisión inválida deja el estado intacto y la pausa vuelve a ofrecerse con el motivo. | `test_una_decision_invalida_no_cambia_el_estado` |

## Pantalla (Streamlit)

| ID | Requisito | Test que lo verifica |
|---|---|---|
| UI-01 | La persona elige con qué rol actúa (`config/people.yaml`, genérico: solo roles, sin nombres) y solo ve los pedidos que le corresponden. | `test_cada_persona_ve_solo_sus_pedidos` |
| UI-02 | Cada pedido muestra el resumen, la evidencia con sus citas (frase, reunión, fecha y orador) y las acciones aprobar, editar y rechazar con comentario. | `test_el_pedido_muestra_la_evidencia_y_las_acciones` |
| UI-03 | Decidir en la pantalla reanuda la corrida y el pedido desaparece de la lista. | `test_decidir_en_la_pantalla_reanuda_la_corrida`, `test_el_recorrido_completo_desde_la_pantalla` |
| UI-04 | La actividad de los agentes se ve mientras ocurre (decisiones, tools y resultados) y el tablero muestra ítems, estados, objeciones y hallazgos. | `test_la_pantalla_muestra_la_actividad_y_el_tablero` |
| UI-05 | El backlog simulado se ve antes y después de publicar. | `test_el_backlog_simulado_se_ve_antes_y_despues` |
| UI-06 | Las corridas guardadas (de la pantalla o de un script) se listan y se pueden abrir en solo lectura: tablero con citas y páginas, hallazgos, registro de decisiones, plan y backlog resultante; no se puede decidir ni reanudar desde ahí. La actividad paso a paso no se guarda: se muestra el recorrido por etapa. | `test_la_pantalla_abre_una_corrida_guardada_en_solo_lectura`, `test_una_corrida_guardada_se_abre_desde_otro_proceso_en_solo_lectura`, `test_iniciar_una_corrida_nueva_sale_del_modo_de_solo_lectura`, `test_la_traza_guardada_se_muestra_por_etapa`, `test_el_backlog_simulado_vuelve_a_leer_el_archivo` |

## Modo demo sin costo (grabación y reproducción)
Una corrida real puede grabarse (las respuestas de cada modelo, en orden) y reproducirse después con proveedores guionados: mismo recorrido, sin red ni costo, determinístico. Sirve para la demo estable y el video de respaldo.

| ID | Requisito | Test que lo verifica |
|---|---|---|
| DM-01 | Grabar una corrida produce un archivo con las respuestas por agente; reproducirlo reproduce el mismo estado final. | `test_grabar_y_reproducir_da_el_mismo_resultado`, `test_la_grabacion_de_la_demo_se_reproduce_de_punta_a_punta` |

## Fuera del curso (decisiones propias)
- Roles de las personas (`people.yaml`) y su control contra la política: la clase 11 trata al actor como identificador de auditoría que no otorga permisos. Aquí **no hay autenticación real**: la persona se elige en la pantalla. Se declara como limitación.
- Agrupación de hallazgos por citas compartidas.
- Interfaz Streamlit y modo grabación y reproducción.
- Dependencia nueva: `streamlit` (extra `ui`).
- Del curso: `ProposedAction` y `HumanDecision` (aquí `DecisionRequest`), `args_hash`, versiones, `interrupt` y `Command(resume=...)` con `SqliteSaver`, y el patrón "revalidar y reautorizar antes de ejecutar".

## Límites conocidos
- La grabación depende de que el flujo haga las mismas llamadas en el mismo orden: si el flujo cambia, hay que volver a grabar (un test lo avisa).
- Streamlit se abre por defecto en todas las interfaces de red: para uso local conviene `--server.address localhost`.
- Aprobar un cambio de alcance solo registra la decisión: no redacta historias nuevas automáticamente. Una corrida posterior puede partir de esa decisión.
- Sin autenticación real ni permisos finos dentro de la pantalla.
- Una corrida a la vez por proceso de la pantalla.
