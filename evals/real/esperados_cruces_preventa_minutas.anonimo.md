# Respuestas esperadas · cruces entre preventa (jun-2026) y minutas 24-08 y 25-08-2026

BORRADOR propuesto por Claude a partir de los 3 PDF. Falta tu revisión: marcá cada fila como OK / NO ES / FALTA.
Este archivo no se versiona (`evals/real/` está en .gitignore). Complementa a `esperados_minuta_2026-08-24.md`.
Convención: P = preventa (diapositiva), M1 = minuta 24-08, M2 = minuta 25-08.

## A. Cambios de alcance respecto de lo vendido (tendría que decidir el service manager)
| # | Lo vendido (preventa) | Lo tratado | Fuente |
|---|---|---|---|
| A1 | Módulo Planificación con rutas, recorridos y optimizador de flota con IA (794 hs) | M2 deja rutas y recorridos fuera del MVP (pendiente de LogiCorp); solo Nodos | P6-8 vs M2 A#1 |
| A2 | Módulo Material electoral y trazabilidad (889 hs) | M1/M2 dejan el Maestro de Materiales en standby/fuera del MVP | P16-17 vs M1 T3, M2 A#1 |
| A3 | Gestión de PA y TT con reclutamiento, bot WhatsApp (Twilio), alta en AFIP y asignación por IA (1135 hs) | M2: el reclutamiento es externo; el backoffice solo recibe la nómina por Excel de columnas fijas; transportistas suspendidos | P9-12, P31 vs M2 T2, A#13-14 |
| A4 | Asignación automática de PA por IA con LLM | M2 la deja como «tarjeta de alcance distinta», solo asignación manual a definir | P11, P31 vs M2 T2 |
| A5 | Comprobantes de pago: carga manual por PA | M1: se descarta la subida individual; ZIP masivo | P13 vs M1 A#17 |
| A6 | Rutas de notificación: alta de envíos por DMS y generación e impresión de piezas | M1: se excluyen plantillas, impresión y emisión física del MVP | P13, P15, P31 vs M1 A#14 |
| A7 | Seguimiento de envíos DMS con 8 estados (admisión … acuse/firma), en tiempo real | M1: 5 estados y actualización dos veces al día, clave DNI + contrato | P14-15 vs M1 A#11 |

## B. Contradicciones entre documentos
| # | Contradicción | Fuente |
|---|---|---|
| B1 | La preventa ofrece «generar versión de maestros para nueva elección» (replicar), pero M1 dice que cada elección se diseña desde cero porque replicar es riesgoso | P6 vs M1 T1 |
| B2 | M1 A#4: sin candados, edición abierta hasta último momento. M2 A#12: candados por módulo controlados por el Super Admin | M1 A#4 vs M2 A#12 |
| B3 | M2 dice que el Maestro de Materiales «quedó fuera de alcance en la sesión anterior», pero M1 lo dejó en standby pendiente de confirmar | M2 T1 vs M1 T3/A#9 |
| B4 | La preventa dice que la liquidación la calcula Oracle HCM vía API. M1 dice que el sistema no calcula montos (los trae el Excel del tribunal) y que la ejecución del pago es externa y está pendiente | P12, P32 vs M1 A#15-16 |
| B5 | La preventa limita el uso de LLM a «dos módulos» pero lista tres (5.1.2, 5.2.2, 5.7.1) | P34 (interna) |
| B6 | La preventa ofrece configurar plantillas y modelos de nota (P13) pero 5.3.3 dice que la impresión es manual de LogiCorp (P31) | P13 vs P31 (interna) |

## C. Inconsistencias internas de las minutas
| # | Detalle | Fuente |
|---|---|---|
| C1 | M1 T3 se titula «Fuera de Alcance» pero el texto dice «standby»; A#9 lo deja en espera. No está cerrado | M1 |
| C2 | M1 A#10 exige como obligatorios el Contrato de Distribución de Urnas y el de Material Electoral, aunque urnas y materiales están fuera o en standby | M1 A#10 vs T3 |
| C3 | M1 A#17 y A#18 dependen de una nomenclatura aún no definida | M1 |
| C4 | M2 A#1 se declara «excluido» y a la vez «pendiente de confirmación por LogiCorp» | M2 |

## D. Compromisos de la preventa que NO se trataron en ninguna minuta (cobertura)
App mobile offline-first, digitalización y OCR de telegramas, escrutinio provisorio con IA, mesa de soporte y monitoreo, dashboards en tiempo real, entornos de prueba, tareas y templates (backoffice), portal de autogestión (login con e-mail y DNI), voluntarios. El sistema debería listarlos como «sin tratar», no como cerrados.

## E. Lo que debería quedar abierto (no como requisito firme)
Materiales, rutas y recorridos y pagos reales (pendientes de LogiCorp); nomenclatura de PDF; envío de muestras de Excel; documentación del TMS.

## F. Ruido que NO debe volverse requisito ni inconsistencia
Marcas «[12, 53]», «[70, 72, 73, 77]», «[84]»; textos de relleno de la preventa («FEATURE Stack Tecnológico – Descripción»); SLA de soporte, horas y plan de trabajo; texto genérico de Azure/Elastic.

## G. Para medir
- Recall y precisión de requisitos contra `esperados_minuta_2026-08-24.md` y las filas de M2 (nodos, nómina, candados).
- Inconsistencias: se espera detectar al menos B1–B4, C1–C2 y A1–A3; falsas alarmas = cualquier otra marcada como contradicción.
- Citas: cada cita debe aparecer textual en el PDF/Word de origen.
- Orden: M1 (24-08) antes que M2 (25-08); B2 solo se detecta si se carga en ese orden.

## H. Minuta del 27-08-2026 (M3): tareas y templates, app móvil y escaneo de DNI offline (BORRADOR, sin revisar)
Requisitos que debería salir:
1. Una «tarea» es un hito macro del Personal de LogiCorp (PA) el domingo y se compone de pasos secuenciales obligatorios.
2. Bloqueo por dependencias y por franja horaria: no se pueden ejecutar hitos futuros antes de tiempo.
3. Categorías de tareas (Transporte, Digitalización, Supervisión) y alta de una categoría nueva desde la propia lista desplegable («Agregar nueva»).
4. El selector de roles se mantiene por escalabilidad, pero el MVP se limita al PA (transportistas excluidos).
5. Solo un rol administrador superior crea y edita tareas y templates.
6. Campos de entrada estándar (texto corto, texto largo, numérico); sin validaciones de audio o video en el MVP.
7. El escaneo de DNI y el autocompletado funcionan local y offline, y se sincronizan en segundo plano al volver la señal.
8. Jerarquía unificada: el Template es la plantilla técnica; la Tarea es su instancia local en cada elección.
9. Ámbitos: repositorio global de templates (edición restringida) y copia local por elección.

Cruces a detectar (a validar):
- H1. **Alcance reducido** frente a la preventa: la preventa vende gestión de PA y TT y mobile para ambos; M2 y M3 dejan a los transportistas fuera del MVP (refuerza A3).
- H2. **Tensión de diseño**: M1 dice que replicar una elección es riesgoso y empieza desde cero; M3 acuerda clonar templates del repositorio global a cada elección (hay que verificar si es una contradicción o solo se trata de plantillas).
- H3. **Pendiente**: el algoritmo de escaneo de DNI heredado está «obsoleto» y se va a analizar con Persona 5; no debe quedar como requisito cerrado.
- H4. **Consistente con la preventa** (no debe ser falsa alarma): bloqueo por ventana horaria y condiciones de foto/geolocalización de las tareas.
- H5. **Preventa omitida**: los templates con campos obligatorios y adjuntos, SLA y recordatorios que vende la preventa (pág. 18) no se trataron; M3 simplifica a tres tipos de campo.
