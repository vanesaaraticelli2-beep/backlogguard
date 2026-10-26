# Especificación · Línea base de la preventa y presupuesto de contexto

**Estado:** Bloque 1A implementado (huella, registro, separación y regla de citas); Bloque 1B y punto 4 propuestos, sin construir · **Código previsto:** `rag/sources.py`, `rag/importers.py`, `rag/compromisos.py` (nuevo), `tools/requerimientos.py`, `tools/critico.py`, `tools/auditor.py`, `agents/decider.py`, `agents/loop.py`, `graph/nodes.py`, `config/context_budget.yaml` y `config/pricing.yaml` (nuevos), `ui/app.py`

## Por qué (datos de la corrida real con Infobae)
- 564 mil tokens en 12,7 minutos. El productor dio **48 pasos para 4 historias**: 32 llamadas a `redactar_historia` (mayormente reescrituras de la misma historia) y 10 búsquedas de unos 7.600 caracteres cada una.
- El Crítico dio **32 pasos para 8 revisiones** (4 por revisión: tres controles y el veredicto), todos con Opus, el modelo más caro.
- Cada paso reenvía **todas** las observaciones anteriores, así que el costo de un agente crece más rápido que su cantidad de pasos.
- El Auditor recibe la preventa completa (unos 52 mil caracteres) en cada corrida y la reenvía en cada uno de sus pasos.
- La preventa se usó como respaldo de una historia (p. 18 y p. 7) mezclada con la evidencia de la reunión.

---

## Punto 1 · Línea base de la preventa

### Qué es
La preventa es la **línea base**: lo que se vendió. Las reuniones son la **evidencia**: lo que se acordó después. La línea base se consulta para comparar, pero no sustenta por sí sola una historia.

### Bloque 1A · Huella, registro y separación — implementado
| ID | Requisito | Test que lo verifica |
|---|---|---|
| LB-01 | Cada fuente guarda una **huella** del texto importado. Importar de nuevo el mismo nombre con el mismo contenido avisa «sin cambios» y no escribe; con otro contenido avisa «cambió» y exige reemplazo explícito. | `test_la_huella_es_estable_y_detecta_cambios`, `test_la_fuente_guarda_su_huella_y_se_verifica_al_cargar`, `test_reimportar_igual_no_escribe_y_distinto_pide_confirmacion`, `test_cambiar_solo_la_fecha_el_nombre_o_el_tipo_tambien_pide_confirmacion`, `test_una_fuente_anterior_a_las_huellas_recibe_la_suya_sin_cambiar_su_contenido` |
| LB-02 | Cada corrida guarda qué fuentes usó (id, tipo, fecha, huella, palabras), y se ve en «Corridas guardadas». | `test_el_inventario_marca_el_rol_de_cada_fuente`, `test_la_corrida_registra_las_fuentes_y_sus_huellas` |
| LB-03 | La búsqueda del productor **excluye la línea base por defecto**; solo la incluye si lo pide con un parámetro explícito. | `test_el_retriever_puede_excluir_por_metadata`, `test_el_productor_no_ve_la_preventa_salvo_que_la_pida` |
| LB-04 | Una historia exige **al menos una cita de evidencia acordada** (reunión o minuta). La preventa puede ser una cita adicional, pero no la única: se rechaza con un mensaje claro. | `test_una_historia_solo_con_preventa_se_rechaza`, `test_la_preventa_como_cita_adicional_se_acepta`, `test_corregir_una_historia_tampoco_puede_quedar_solo_con_preventa` |
| LB-05 | El Crítico comprueba ese respaldo con un control determinístico más en DoR/INVEST (`respaldo_acordado`). | `test_el_critico_marca_la_historia_sin_respaldo_acordado` |
| LB-06 | La pantalla distingue «Línea base» de «Evidencia» en la evidencia de los pedidos y en las citas del tablero. | `test_la_evidencia_de_un_pedido_lleva_el_tipo_de_fuente`, `test_la_pantalla_distingue_linea_base_y_evidencia_y_muestra_las_fuentes_de_la_corrida` |

**Decisiones tomadas al construir:** la huella se guarda en la fuente y se verifica al cargarla (una edición a mano se avisa); pedir la preventa por tipo o por documento alcanza sin la bandera extra; cambiar solo el nombre, la fecha, el tipo o el formato cuenta como «cambió» y pide confirmación; una fuente anterior a las huellas recibe la suya sin que se toque su contenido.

**Qué NO cambia:** el Auditor sigue siendo el único agente que compara la línea base completa contra las reuniones. Las historias que surgen de algo solo vendido (por ejemplo, una integración con el ERP que nadie habló) siguen siendo hallazgos para una persona, no historias automáticas.

### Bloque 1B · Compromisos de la preventa (se extraen una sola vez)
La preventa se resume **una vez** en una lista de compromisos, cada uno con su página y su cita literal. Esa lista se guarda ligada a la huella y se reutiliza mientras la preventa no cambie.

| ID | Requisito | Test previsto |
|---|---|---|
| LB-07 | La extracción es **explícita** (botón o comando), muestra una estimación del gasto antes de correr y necesita modelos reales. Nunca corre sola. | `test_la_extraccion_no_corre_sin_confirmacion_ni_sin_modelos` |
| LB-08 | Cada compromiso lleva página y una **cita literal verificada** contra el texto de esa página; los que no se verifican se **descartan y se informan**. | `test_un_compromiso_con_cita_falsa_se_descarta_y_se_informa` |
| LB-09 | El resultado queda guardado con la huella: se reutiliza mientras no cambie y **se invalida** cuando la preventa cambia. | `test_los_compromisos_se_reutilizan_con_la_misma_huella`, `test_cambiar_la_preventa_invalida_los_compromisos` |
| LB-10 | Si hay compromisos válidos, el Auditor los usa en lugar de la preventa completa (el texto de una página se pide solo si lo necesita); si no hay, usa el camino actual. La corrida registra cuál usó. | `test_el_auditor_usa_los_compromisos_si_existen`, `test_sin_compromisos_el_auditor_usa_la_preventa_completa` |
| LB-11 | La pantalla muestra la lista de compromisos extraídos, con su página y su cita (solo lectura en esta versión). | `test_la_pantalla_lista_los_compromisos` |

**Riesgo principal:** que la extracción omita compromisos y el Auditor deje de detectar algo «vendido y no tratado». Mitigación: verificación determinística de las citas, lista visible para revisarla y el camino de la preventa completa como alternativa.

---

## Punto 4 · Presupuesto de contexto sin perder trazabilidad

### Principios
1. **La traza nunca se achica.** Lo que se compacta es el *prompt*; las observaciones completas siguen guardadas en la traza y en el estado.
2. **El resumen no es evidencia.** Las citas se validan contra los fragmentos del índice (existencia y texto literal), no contra lo que el modelo recuerda del prompt.
3. **Resúmenes determinísticos, no escritos por un modelo.** Un modelo que resume puede inventar; una regla fija no.

### Palancas, de mayor a menor beneficio frente al riesgo
| ID | Palanca | Qué hace | Ahorro esperado (a medir) |
|---|---|---|---|
| CX-01 | **Medición** | Registra por agente y por paso las llamadas, los tokens de entrada y de salida y el costo estimado (con `config/pricing.yaml`). Se ve en el estado, en «Corrida» y en «Corridas guardadas». | Ninguno directo: es lo que permite probar el resto. |
| CX-02 | **Tope de reescrituras** | Un ítem se corrige como máximo 2 veces por corrida; la tercera se rechaza con un mensaje. | Hasta ~25 de las 32 llamadas de redacción de la corrida real. |
| CX-03 | **Expediente del Crítico** | Sus tres controles (DoR/INVEST, verificación de citas y contraevidencia) los ejecuta el código antes de llamar al modelo y llegan juntos en el primer prompt. El modelo puede pedir más evidencia con otra consulta. | De 4 pasos con Opus a 1 o 2 por revisión. |
| CX-04 | **Expediente del Auditor** | Igual: la comparación con la preventa, las contradicciones y las decisiones vigentes llegan precalculadas. | De 3 o 4 pasos a 1 o 2, sin reenviar 66 mil caracteres en cada uno. |
| CX-05 | **Compactación del historial** | Las observaciones se mantienen completas solo en una ventana (por defecto las 2 últimas); las anteriores se reducen a una línea fija por tipo de herramienta. | Fuerte en el productor, que tiene crecimiento cuadrático. |
| CX-06 | **Presupuesto de contexto por agente** | `config/context_budget.yaml` fija la ventana y el tope de prompt de cada agente; si se supera, se comprime más y queda registrado. | Evita desbordes con documentos grandes. |
| CX-07 | **Caché de prompts del proveedor** (opcional) | Reutiliza el prefijo estable (instrucciones y herramientas). Hay que verificar sus condiciones con los modelos actuales antes de construirlo; la compactación cambia mensajes anteriores y no deja cachear lo que no sea el prefijo fijo. | Menor que las otras, sin riesgo de trazabilidad. |

**Descartado:** resúmenes escritos por un modelo.

### Cómo se compactan las observaciones antiguas (CX-05)
| Herramienta | Qué queda en el prompt cuando ya es antigua |
|---|---|
| `buscar_en_fuentes`, `buscar_contraevidencia` | Por cada fragmento: id, fuente, página y los primeros 120 caracteres. El texto completo se vuelve a pedir buscando de nuevo. |
| `redactar_historia` | El resultado completo (es de una línea). |
| `evaluar_dor_invest`, `verificar_cita` | Solo los controles que fallaron y los veredictos. |
| `comparar_con_preventa`, `detectar_contradicciones` | Los ids de lo que ya se analizó y los hallazgos ya formulados. |

### Requisitos
| ID | Requisito | Test previsto |
|---|---|---|
| CX-08 | La medición separa agente, modelo y paso, suma al total de la corrida y calcula el costo estimado; con un modelo sin precio configurado avisa en lugar de inventar un valor. | `test_la_medicion_es_por_agente_y_calcula_el_costo`, `test_un_modelo_sin_precio_se_avisa` |
| CX-09 | Un ítem no se corrige más de 2 veces por corrida. | `test_la_tercera_correccion_se_rechaza` |
| CX-10 | El Crítico recibe sus controles precalculados, que quedan en la traza marcados como precalculados; los ejecuta el `ToolRegistry` con la política habitual. | `test_el_critico_recibe_el_expediente_y_la_traza_lo_registra` |
| CX-11 | El Auditor recibe su expediente precalculado en un solo prompt. | `test_el_auditor_recibe_el_expediente` |
| CX-12 | La compactación respeta la ventana configurada y las reglas por herramienta; un digest nunca contiene texto que no esté en la observación original y conserva todos los ids de fragmentos. | `test_la_compactacion_respeta_la_ventana`, `test_un_digest_no_agrega_texto_y_conserva_los_ids` |
| CX-13 | La traza y las observaciones guardadas conservan el contenido completo aunque el prompt esté compactado. | `test_la_traza_conserva_las_observaciones_completas` |
| CX-14 | La validación de citas no depende del prompt: una cita a un fragmento que ya no figura en el prompt se valida igual contra el índice. | `test_una_cita_se_valida_contra_el_indice_y_no_contra_el_prompt` |
| CX-15 | **Guarda de calidad:** con y sin expediente y compactación, el Crítico da el mismo veredicto sobre los ítems sembrados con errores, y el productor reproduce las mismas historias sobre la corrida grabada. | `test_el_critico_da_los_mismos_veredictos_con_y_sin_expediente`, `test_la_grabacion_sigue_reproduciendose` |
| CX-16 | El tope de contexto por agente se respeta y, si se supera, se registra. | `test_el_tope_de_contexto_comprime_y_lo_registra` |

## Fuera del curso (decisiones propias)
- Extracción de compromisos de la preventa y su verificación (el curso no la tiene).
- **Expediente precalculado:** se aparta del ciclo puro Decide → Act → Observe de la clase 9, porque ciertas herramientas las ejecuta el código antes de la primera decisión. Cada ejecución pasa por el `ToolRegistry` y queda en la traza. Se acerca a la idea de «constructor de contexto» de la clase 10.
- `config/pricing.yaml` con precios por millón de tokens (valores a verificar con el proveedor).
- `config/context_budget.yaml` ya figuraba en el README; acá se define su contenido.

## Límites conocidos (previstos)
- Los ahorros indicados son estimaciones: se confirman con la medición (CX-01) sobre la misma corrida antes y después.
- La línea base admite una sola versión por preventa; una adenda se importa como fuente nueva y la elección de cuál es la vigente es manual.
- La compactación puede obligar al productor a buscar de nuevo un fragmento que ya no ve: cuesta un paso, pero no compromete la evidencia.
- No se resuelve acá la identidad estable de las historias entre corridas (punto 2 de la evaluación anterior).
