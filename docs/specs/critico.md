# Especificación · Agente Crítico

**Estado:** implementado (Día 6) · **Modelo:** `claude-opus-5-5`, esfuerzo medio (distinto proveedor que el productor) · **Código:** `src/backlogguard/agents/critico/`, `agents/negociacion.py`, `tools/critico.py`

## Propósito
Revisar de forma adversarial cada ítem del productor y objetar lo que no esté bien sustentado. No es el autor: no reescribe. Un acuerdo se alcanza en un máximo de **2 rondas**; si no, decide una persona.

## Entradas y salidas
- **Entrada:** el `item_id` a revisar. El contenido del ítem le llega como observación de una tool (dato no confiable), no en el objetivo.
- **Tools (3, solo lectura y cálculo):** `verificar_cita`, `buscar_contraevidencia`, `evaluar_dor_invest`.
- **Salida:** `CriticVerdict` validado con Pydantic: `sustentado` u `objetado`, con las objeciones concretas. El Crítico **no escribe** en el tablero: la aplicación aplica el veredicto.

## Requisitos

| ID | Requisito | Test que lo verifica |
|---|---|---|
| CR-01 | La verificación de citas es determinística: la frase debe figurar en el fragmento (se ignoran espacios, mayúsculas y comillas; no acentos ni palabras), y la reunión y la fecha deben coincidir. | `test_normalizacion_ignora_formato_pero_no_acentos_ni_palabras`, `test_cita_textual_pasa_aunque_cambien_espacios_y_mayusculas`, `test_cita_deformada_falla`, `test_cita_con_fragmento_inexistente_o_metadata_distinta`, `test_verificar_cita_como_tool` |
| CR-02 | La contraevidencia excluye lo que el ítem ya cita y marca lo más reciente que la cita. | `test_contraevidencia_encuentra_la_reunion_posterior_y_excluye_lo_citado` |
| CR-03 | El control DoR/INVEST es objetivo: citas, formato Como/quiero/para, Gherkin, tamaño (≤ 5 criterios) y posibles duplicados. | `test_dor_invest_aprueba_un_item_bien_formado`, `test_dor_invest_marca_formato_gherkin_tamano_y_duplicados` |
| CR-04 | Solo el Crítico ve sus tools y ninguna escribe. | `test_las_tools_del_critico_son_solo_del_critico_y_no_escriben` |
| CR-05 | El veredicto es coherente (un objetado necesita objeciones; un sustentado no las lleva), es del ítem pedido y, si viene mal formado, se repara una vez. | `test_veredicto_exige_coherencia`, `test_agente_critico_devuelve_un_veredicto_validado`, `test_veredicto_invalido_se_repara_una_vez_y_luego_falla` |
| CR-06 | Si el Crítico no llega a un veredicto (agota pasos), falla de forma explícita; no se asume nada. | `test_el_critico_no_llega_a_veredicto_si_agota_pasos` |
| CR-07 | Aprobado en la ronda 1, o corrección y acuerdo en la ronda 2, con las objeciones resueltas registradas. | `test_aprobado_en_la_primera_ronda`, `test_objecion_correccion_y_acuerdo_en_la_segunda_ronda` |
| CR-08 | Sin acuerdo tras 2 rondas no hay tercera: el ítem queda objetado (`sin_consenso`) para que decida una persona. | `test_sin_consenso_tras_dos_rondas_no_hay_tercera`, `test_el_tope_de_rondas_no_se_puede_superar` |
| CR-09 | Una cita que no se verifica impide `sustentado`, aunque el modelo lo apruebe. | `test_una_cita_falsa_anula_el_sustentado_del_modelo` |

## Fuera del curso (decisiones propias)
- El Crítico no escribe y el código aplica sus veredictos (patrón Command).
- Veredicto estructurado, verificación determinística de citas y detección de duplicados por similitud de títulos.
- Modelo de otro proveedor que el productor, validado por `config/models.yaml`.

## Límites conocidos
- Opus es estricto con criterios Gherkin genéricos; se mide en la evaluación (Día 13).
- La negociación completa con el productor real no se probó por falta de cuota de Gemini; los tests usan respuestas guionadas.
- El juicio de si algo contradice o sustenta es del modelo y no es determinístico.
