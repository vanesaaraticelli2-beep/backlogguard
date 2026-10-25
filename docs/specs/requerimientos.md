# Especificación · Agente de Requerimientos (productor)

**Estado:** implementado (Día 5) · **Modelo:** `gemini-3.8-flash` (`config/models.yaml`) · **Código:** `src/backlogguard/agents/requerimientos/`, `tools/requerimientos.py`, `rag/`

## Propósito
Convertir el material de reuniones y preventa en ítems de backlog (épica, historia, tarea, caso de prueba) redactados con criterios de aceptación en Gherkin y respaldados por citas textuales. Todo lo que crea queda en estado **borrador**.

## Entradas y salidas
- **Entrada:** un objetivo en texto y una biblioteca de fuentes (`evals/fixtures/`, archivos `.md` con metadata en el encabezado).
- **Tools (3):** `ingestar_y_fragmentar` (`local_write`), `buscar_en_fuentes` (`read`), `redactar_historia` (`local_write`).
- **Salida:** ítems `BacklogItem` en el tablero + una respuesta final que resume qué creó, qué dejó sin redactar y qué instrucciones sospechosas vio.

## Requisitos

| ID | Requisito | Test que lo verifica |
|---|---|---|
| RQ-01 | Solo lee fuentes de la biblioteca, por `document_id` válido. Una ruta o un id inexistente se rechaza. | `test_ingesta_rechaza_ids_peligrosos_e_inexistentes`, `test_biblioteca_rechaza_ids_invalidos_o_inexistentes` |
| RQ-02 | Fragmenta por turno de orador y conserva quién habló y dónde; los ids de fragmento son estables. | `test_turnos_conservan_orador_y_posicion`, `test_chunks_con_metadata_e_ids_estables`, `test_turno_largo_se_parte_sin_perder_orador` |
| RQ-03 | La búsqueda devuelve texto con reunión, fecha y orador, y admite filtros por tipo de fuente o documento. | `test_busqueda_devuelve_lo_relevante_con_metadata`, `test_filtros_por_metadata`, `test_busqueda_filtra_por_tipo_de_fuente` |
| RQ-04 | Volver a indexar una fuente reemplaza la versión anterior. | `test_get_y_reindexado_reemplaza_el_documento` |
| RQ-05 | Todo ítem lleva al menos una cita a un fragmento que existe; la reunión, la fecha y el orador de la cita salen del fragmento, no del modelo. | `test_redactar_arma_la_cita_con_la_metadata_del_fragmento`, `test_redactar_rechaza_citas_inexistentes_sin_gherkin_y_sin_citas` |
| RQ-06 | Los criterios de aceptación deben ser Gherkin (Dado/Cuando/Entonces). | `test_redactar_rechaza_citas_inexistentes_sin_gherkin_y_sin_citas` |
| RQ-07 | No crea dos ítems con el mismo tipo y título. | `test_redactar_no_duplica_el_mismo_item` |
| RQ-08 | Solo este rol ve sus tools; ningún otro puede redactar. | `test_solo_requerimientos_ve_estas_tools`, `test_el_catalogo_rechaza_tools_desconocidas` |
| RQ-09 | El texto de las reuniones es dato: una orden dentro de un fragmento no se ejecuta (llega delimitada como no confiable). | `test_inyeccion_en_la_reunion_es_dato_y_no_orden` |
| RQ-10 | Corta por presupuesto de pasos, tiempo, llamadas a tools y tokens. | `test_el_agente_respeta_el_tope_de_tool_calls`, `test_agente_completo_con_respuestas_guionadas` |
| RQ-11 | Puede corregir un ítem **objetado** (`revises`) conservando su id y sus objeciones; no corrige ítems que no están objetados. | `test_revises_corrige_un_item_objetado_conservando_id_y_objeciones`, `test_revises_rechaza_items_inexistentes_o_no_objetados` |

## Fuera del curso (decisiones propias)
- Biblioteca de fuentes con metadata en el encabezado y chunking por turnos de orador (el curso corta por palabras y oraciones).
- Corrección de un error de la clase 5: con `overlap_words=0`, `recursive_chunks` duplicaba el chunk anterior.
- Historia estructurada con Pydantic y parámetro `revises`.

## Límites conocidos
- Detecta duplicados solo cuando el título es idéntico; los casi duplicados los marca el Crítico.
- Embeddings determinísticos (léxicos): la búsqueda no entiende sinónimos. Los reales se miden en la evaluación.
- Con Gemini en el plan gratuito, la cuota de 20 pedidos por día limita las corridas reales.
