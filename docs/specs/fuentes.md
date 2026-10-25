# Especificación · Carga de fuentes propias (preventa en PDF y transcripción en texto)

**Estado:** implementado · **Código:** `src/backlogguard/rag/importers.py`, `rag/chunking.py`, `rag/sources.py`, `rag/lexical.py`, `ui/app.py` (pestaña «Fuentes»), `graph/setup.py` y `scripts/importar_fuentes.py`

## Propósito
Poder correr el sistema con **documentos reales del usuario**: una preventa en PDF y la transcripción de una reunión en texto. Hoy los agentes solo leen las fuentes de ejemplo de `evals/fixtures/`.

## Cómo entra una fuente
1. La persona sube o pega el documento en la pestaña **Fuentes** y completa el nombre, la fecha y el tipo (preventa, reunión o minuta).
2. El importador lo convierte a texto y lo valida.
3. Se guarda en `data/fuentes/` como un `.md` con la metadata en el encabezado, igual que las fuentes de ejemplo. `data/` no se sube a git.
4. La corrida usa `data/fuentes/` cuando hay al menos una preventa y una reunión; si no, usa las de ejemplo. La pantalla muestra cuál está usando.

## Requisitos

| ID | Requisito | Test que lo verifica |
|---|---|---|
| FU-01 | Un PDF con texto se importa página por página. Un PDF sin texto (escaneado) o dañado se rechaza con un mensaje claro: el reconocimiento de texto en imágenes (OCR) no está incluido. | `test_un_pdf_con_texto_se_importa_por_pagina`, `test_un_pdf_escaneado_o_danado_se_rechaza` |
| FU-02 | Una transcripción en texto se importa en UTF-8 o Latin-1 y se normalizan los formatos de línea más comunes: `Nombre: texto`, `[00:12:30] Nombre: texto` y `Nombre 00:12` seguido del texto en la línea siguiente. | `test_la_transcripcion_acepta_los_formatos_mas_comunes`, `test_el_encabezado_no_es_conversacion_y_los_oradores_reciben_su_rol` |
| FU-03 | Nombre, fecha y tipo son obligatorios y se validan; el identificador se deriva del nombre y no puede salirse de `data/fuentes/` ni pisar otra fuente sin confirmar. | `test_la_metadata_es_obligatoria`, `test_el_identificador_no_sale_de_la_carpeta_ni_pisa_otra_fuente` |
| FU-04 | La preventa no se divide por «orador»: una línea como `Alcance: portal de autoservicio` no se confunde con alguien que habla. Se fragmenta por párrafos y oraciones y conserva el número de página. | `test_la_preventa_no_inventa_oradores_y_conserva_la_pagina`, `test_el_dialogo_agrupa_pregunta_y_respuesta_y_conserva_los_oradores` |
| FU-05 | Una transcripción sin el formato «Orador: texto» se acepta, pero la pantalla avisa que las citas quedarán sin atribución. | `test_una_transcripcion_sin_oradores_avisa` |
| FU-06 | Las citas de la preventa muestran la página (por ejemplo, «Propuesta comercial, p. 3»), y el Crítico y el Auditor las verifican igual que las demás. | `test_la_cita_de_la_preventa_muestra_la_pagina_y_el_critico_la_verifica` |
| FU-07 | Hay un tope de tamaño (páginas, palabras y megabytes). Si se supera, se rechaza con el motivo y no se gasta nada. | `test_un_documento_demasiado_grande_se_rechaza` |
| FU-08 | Antes de correr con modelos reales, la pantalla estima el tamaño (palabras, fragmentos y tokens aproximados) y recuerda el tope de tokens por corrida. | `test_la_estimacion_antes_de_correr` |
| FU-09 | Con fuentes propias no se cargan los work items de ejemplo, y la corrida exige `LIVE_MODE=1`: la grabación no sabe responder a documentos nuevos. | `test_con_fuentes_propias_no_se_siembran_ejemplos_y_exige_modelos_reales` |
| FU-10 | El texto importado sigue siendo dato no confiable: una orden dentro del PDF o de la transcripción se cita, no se obedece. | `test_una_orden_dentro_de_un_pdf_se_trata_como_dato` |
| FU-11 | Se puede ver, borrar y volver a las fuentes de ejemplo desde la pantalla. | `test_ver_borrar_y_volver_a_las_fuentes_de_ejemplo` |
| FU-12 | Con documentos reales la búsqueda combina embeddings y BM25 con fusión RRF; las variantes de una palabra («filtro», «filtrar») coinciden. | `test_las_raices_unen_variantes_y_se_ignoran_acentos_y_palabras_vacias`, `test_bm25_prefiere_los_terminos_raros_y_rrf_fusiona_los_rankings`, `test_la_busqueda_hibrida_encuentra_lo_que_los_embeddings_ordenan_mal` |
| FU-13 | Con los archivos reales de la prueba (si están en `entrada/`), el PDF se lee con 37 páginas y la transcripción con sus 4 oradores y sus roles. | `test_la_preventa_real_se_importa_con_paginas_y_texto`, `test_la_transcripcion_real_se_importa_con_oradores_y_roles` |

## Fuera del curso (decisiones propias)
- Importación de PDF y de transcripciones, y la pestaña de carga.
- Dependencia nueva: `pypdf` (Python puro, sin OCR).
- Número de página en las citas de la preventa (cambio menor al contrato de `Citation`).
- Fragmentado por páginas y por diálogo (intervenciones seguidas juntas).
- Del curso: el chunking y la metadata por fragmento (clase 5) y la búsqueda BM25 con fusión RRF (clase 8), adaptada al español (raíz de 5 letras, palabras vacías, sin acentos, sin `rank-bm25`).

## Límites conocidos
- Sin OCR: un PDF que es una imagen escaneada no se puede leer.
- Tablas, columnas y gráficos de un PDF se extraen como texto lineal y pueden salir desordenados; hay que revisar la vista previa antes de correr.
- Word (`.docx`) y otros formatos quedan fuera.
- Los embeddings siguen siendo léxicos; la búsqueda híbrida compensa buena parte, pero una preventa con vocabulario muy distinto al de la reunión se relaciona peor. Los embeddings reales se miden en la evaluación.
- Con documentos de este tamaño el Auditor lee una comparación recortada (cada fragmento a 300 caracteres): es un resumen de evidencia, no el texto completo.
- Los documentos viajan a los proveedores de los modelos (Anthropic y, si se usa, Gemini).
