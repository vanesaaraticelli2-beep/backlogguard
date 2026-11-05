---
source_name: Propuesta TechPartner - Proyecto LogiCorp - DMS Elecciones
source_type: preventa
source_date: '2026-06-01'
layout: paginas
fingerprint: 703c66e5c00660c4
---
[[página 3]]
Sección de imagen 
referencial del cliente
Contexto actual
3
LogiCorp es una empresa de logística que opera como proveedor de servicios 
electorales para organismos gubernamentales y entes electorales en Argentina. 
Su negocio electoral implica la planificación y ejecución de operaciones de 
altísima complejidad logística: distribución y recolección de materiales 
electorales (urnas, kits, documentación), gestión de personal de LogiCorp (PA) y 
transportistas (TT), coordinación de autoridades de mesa, digitalización de 
telegramas y transmisión de resultados a Juntas Electorales, todo en plazos 
extremadamente acotados y con alta demanda de trazabilidad y 
confiabilidad.
LogiCorp requiere una plataforma unificada que cubra de forma cohesiva 
todos los frentes operativos del proceso electoral: desde la planificación 
logística previa, pasando por la operación en campo el día de la elección, hasta 
el recuento/escrutinio provisorio y retorno de las urnas para el escrutinio final.
La falta de integración entre módulos, la ausencia de capacidades de IA para 
optimización y procesamiento de telegramas, y la necesidad de soportar 
operación mobile offline-first en establecimientos con conectividad limitada 
son las necesidades centrales encontradas.

[[página 5]]
Objetivo general
La solución propuesta es una Plataforma de Gestión Integral de Operaciones 
Electorales que cubre todas las etapas del proceso electoral: planificación logística, 
gestión de personal, coordinación de autoridades de mesa, trazabilidad de materiales, 
operación mobile en campo, digitalización y transmisión de telegramas, escrutinio 
provisorio asistido por IA y monitoreo en tiempo real.
Qué incluye el alcance:
• Planificación end-to-end con maestro de nodos, rutas y recorridos, optimizador de 
flota con IA y gestión de expedición.
• Gestión completa de PA y TT: reclutamiento, asignación geolocalizada (IA), 
administración, orden de pagos y trazabilidad de liquidaciones de pago.
• Coordinación del proceso electoral: maestro, padrón, notificaciones DMS, portal de 
autogestión web y voluntarios.
• Módulo de material electoral con trazabilidad, auditoría, armado/finishing y rendición.
• Backoffice operativo con gestión de tareas y templates configurables.
• Aplicación Mobile offline-first para PA y TT con geolocalización y escaneo de DNI
• Digitalización de telegramas en aplicación mobile: captura en 
establecimientos (OCR) y banco digital en nodos, con transmisión a Juntas 
Electorales.
• Módulo de escrutinio provisorio y contabilización con IA: parseo automatizado de 
telegramas, precarga de resultados y detección de anomalías.
• Mesa de soporte y monitoreo con gestión de incidencias, tickets, alertas y reportes 
operativos.
• Transversales: dashboards en tiempo real, seguridad y roles, auditoria, soporte 
multielección y entornos de prueba. 5

[[página 6]]
Maestro de nodos, rutas y recorridos
- Crear, editar y eliminar nodos, rutas y recorridos 
- Importar masivamente nodos, rutas y recorridos
- Generar versión de maestros para nueva elección
- Configurar parámetros independientes por elección
- Definir relaciones jerárquicas entre nodos, rutas y recorridos
Planificación de la expedición
- Crear rutas de abastecimiento a nodo
- Asociar recorridos, escuelas y transportistas por ruta
- Parametrizar medidas de pallet (alto, ancho, largo, peso)
- Definir reglas configurables de armado de contenedor
- Definir criterio de corte de pallet
Pre-elección
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Planificación
Arquitectura e integraciones
Coordinador 
de nodo
Ccoordinador 
planificación
Planificación de la 
expedición
- Consultar estado de 
recorridos activos
Elección Apertura de escrutinio prov Escrutinio prov
Pilares del negocio
El modulo de Planificación agrupa las funcionalidades que permiten planificar operativamente la elección antes del día de votación: definición de nodos y rutas, 
optimización de flota con IA y planificación de expedición de materiales. Operan principalmente el equipo de planificación, coordinación y operativos de LogiCorp
6
Integraciones
- API Google OR tools/Google Maps APIs
- API LLM
Planificación de la expedición
- Definir layout de zona de trabajo (sectores y posiciones)
- Crear y gestionar contenedores por ruta
- Generar tareas operativas de picking y armado
- Controlar materiales nominados y no nominados por 
contenedor
Optimizador de flota y recorridos (IA)
- Solicitar optimización de flota y recorridos
Armadores
Planificación de la expedición
- Ejecutar picking por escaneo QR / Code128 o manual
- Ejecutar doble control al pickear material
- Confirmar armado de pallet o contenedor
Maestro de nodos, rutas 
y recorridos
- Revisar trazabilidad de 
cambios en maestros
Post-escrutinio prov

[[página 7]]
Arquitectura e integraciones
Procesos automáticos
✓ Modulo Planificación
El sistema dentro del modulo debe poder:
Maestro de nodos, rutas y recorridos
• Aplicar reglas de validación al importar
• Registrar trazabilidad de cambios en maestros
Optimizador de flota y recorridos (IA)
• Calcular carga y capacidad por recorrido
• Analizar caminos y accesibilidad geográfica
• Proponer combinación óptima de unidades de transporte (optimizador IA)
• Recomendar tipo de unidad de transporte por recorrido
Planificación de la expedición
• Calcular automáticamente necesidades de materiales por escuela/recorrido
• Generar automáticamente tareas de abastecimiento
• Priorizar tareas por fecha/hora límite y criticidad 7

[[página 8]]
Arquitectura e integraciones
Integraciones a Desarrollar
Modulo Planificación
✓ API LLM
Optimizador de flota y recorridos
El sistema utiliza una API de modelo de lenguaje de gran escala (LLM) como capa de razonamiento e interpretación sobre los resultados del 
optimizador de rutas, permitiendo traducir las salidas matemáticas del algoritmo VRP en recomendaciones operativas comprensibles y 
justificadas para el equipo de planificación. El objetivo es asistir a los coordinadores logísticos en la toma de decisiones sobre flota y 
recorridos, combinando la precisión del optimizador con la capacidad del LLM para contextualizar, explicar y adaptar las propuestas al 
lenguaje operativo de LogiCorp.

[[página 9]]
Reclutamiento de PA
- Visualizar y filtrar candidatos por edad, celular, domicilio 
y disponibilidad
- Registrar notas screening telefónico o mecanismo 
alternativo
- Dar de alta manualmente a candidato PA
- Identificar y gestionar candidatos con doble rol (PA + TT)
- Asociar candidato preseleccionado a un nodo
Gestión administrativa de PA 
- Visualizar seguimiento de capacitación presencial
Pre-elección
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Gestión de PA y TT
Arquitectura e integraciones
Coordinador 
de nodo
RRHH
Reclutamiento y onboarding TT
- Registrar posiciones de transportistas 
necesarias
- Verificar documentación de TT
- Dar de alta al transportista en el 
sistema
Asignación inteligente de TT
- Vincular transportista a recorrido 
planificado segun necesidad operativa
Pago a transportistas por liquidación
- Adaptar liquidación de TT para 
esquema de pago electoral
Pilares del negocio
El modulo de Gestión de PA y TT agrupa todos las funcionalidades relacionadas con el reclutamiento, selección, asignación, capacitación, administración y pago del 
personal electoral: Padrón de LogiCorp (PA) y Transportistas (TT), así como personal interno. Operan principalmente RRHH, coordinadores de nodo, PA y gerentes/jefes.
9
Integraciones
- AFIP/ARCA – Alta de trabajador (Proceso 
existente LogiCorp)
- Servicio CPaaS
- API Google OR tools/Google Maps APIs
- API LLM
- API liquidación de pagos a transportistas
• API liquidación de pagos a PA
Asignación manual de PA
- Asignar o modificar asignación de PA a cada colegio
- Visualizar en mapa colegios, nodos y domicilio de 
personas
- Segregar candidatos con y sin movilidad propia
- Generar y visualizar sugerencia automática por IA 
de asignación de PA para cada colegio
- Visualizar medios de transporte sugeridos para PA
- Visualizar personas con doble rol en el mapa
Gerente
/ jefe
Post-escrutinio prov
Candidato 
PA
 Reclutamiento de PA
- Registrar postulación digital (onboarding)
- Interactuar con chatbot
PA
Reclutamiento y selección de 
personal interno
- Aprobar / Rechazar candidato 
Reclutamiento y 
selección de 
personal interno
- Cargar 
candidaturas de 
personal interno
- Seleccionar 
candidato según 
experiencia en 
elecciones y 
evaluaciones
Gestión administrativa de PA (pagos 
y materiales)
- Modificar datos de cuenta bancaria 
propia
Gestión administrativa 
de PA (pagos y 
materiales)
- Registrar medios de 
pago alternativos de 
PA
- Modificar datos de 
cuenta de PA
Reclutamiento y selección de 
personal interno
- Recibir notificación de resultado de 
candidatura
Gestión administrativa de PA (pagos y 
materiales)
- Registrar manualmente confirmación 
de pago (fecha, monto, medio, 
responsable) 
- Confirmar suplencias y dobles 
asignaciones para pago
- Importar archivo CSV/XLSX con 
estados de pago
- Consultar estado de pago de cada 
PA
- Enviar detalle de orden de pago final 
a PA via API
Reclutamiento y selección de personal 
interno
- Registrar evaluación de desempeño
- Registrar pago por servicio
Pago a transportistas por liquidación
- Enviar detalle de orden de pago final 
a transportistas via API

[[página 10]]
Arquitectura e integraciones
Procesos automáticos
10
✓ Modulo Gestión de PA y TT
El sistema dentro del modulo debe poder:
Reclutamiento de PA
• Ejecutar bot de WhatsApp (Twilio) para interacción inicial, validación de datos, 
screening automatizado y confirmación de disponibilidad del candidato
Asignación automática de PA (IA)
• Proponer PA más adecuados para cada colegio mediante IA geolocalizada
Asignación manual de PA
• Calcular tiempo de viaje entre domicilio del PA y colegio
• Restringir que cada nodo modifique solo sus candidatos
Gestión administrativa de PA 
• Disparar alta en AFIP a partir de foto de DNI (utilizando Servicio de LogiCorp)
• Enviar carátula y formularios al PA por WhatsApp o mail
• Actualizar resultado de examen de capacitación vía API
• Generar baja de alta temprana durante el día de la elección en caso de no 
presentación
Reclutamiento y selección de personal interno
• Enviar aviso al candidato seleccionado
Gestión administrativa de PA (pagos y materiales)
• Cargar datos desde archivo CSV/XLSX con autoridades de mesa junto con el 
estado de pago de las mismas y validar estado de pago de cada PA
• Monitorear estados de pago (pendiente, en proceso, aprobado, pagado, 
rechazado) y enviar alertas automáticas ante demoras o inconsistencias

[[página 11]]
Arquitectura e integraciones
Integraciones a Desarrollar
Modulo Gestión de PA y TT
✓ AFIP / ARCA
Alta de personal PA
El sistema envía los datos del PA a la integración existente de AFIP/ARCA con 
LogiCorp, espera confirmación y actualiza el estado en el maestro de personal
✓ API Google OR tools/Google Maps APIs
Optimización de rutas, cálculo de distancias y datos geográficos
El sistema utiliza las APIs de Google para resolver dos problemas distintos pero 
complementarios dentro de la operación electoral. Por un lado, Google OR-Tools 
provee el motor de optimización combinatoria para calcular la distribución óptima 
de flota y recorridos minimizando kilómetros y tiempos ociosos. Por otro lado, 
Google Maps APIs aporta los datos geográficos reales — calles, accesibilidad, 
tiempos de viaje
✓ API LLM
Generar sugerencia de asignación de PA a cada colegio mediante IA geolocalizada
El sistema utiliza una API de modelo de lenguaje de gran escala (LLM) como motor 
de razonamiento para la asignación inteligente de PA a cada colegio electoral. A 
partir de los datos de domicilio, disponibilidad, movilidad, doble rol y distancia de 
cada candidato PA, el LLM analiza el conjunto de variables de forma contextual y 
genera una propuesta de asignación optimizada que un operador de RRHH puede 
revisar, ajustar y confirmar.
✓ Servicio CPaas (ej Twilio)
Mensajes de notificación y respuestas de bot
El sistema envía mensajes de notificaciones a Candidatos PA y utilización de 
interface para Chatbot

[[página 12]]
Arquitectura e integraciones
Integraciones a Desarrollar
Modulo Gestión de PA y TT
✓ API liquidación de pagos a transportistas
Enviar información y novedades para realizar liquidación de pagos a transportistas
El sistema se integra con la API del módulo de liquidación de transportistas existente de LogiCorp para transmitir toda la información operativa y las novedades 
generadas durante el proceso electoral que son necesarias para calcular y ejecutar el pago a cada transportista. El objetivo es garantizar que el sistema de liquidación 
existente de LogiCorp reciba los datos de los recorridos efectivamente realizados, las horas trabajadas, las suplencias, los dobles roles y cualquier novedad que impacte 
en el monto final a liquidar
✓ API liquidación de pagos a PA
Enviar información y novedades para realizar liquidación de pagos a PA
El sistema se integra con la API del módulo de liquidación de pagos existente de LogiCorp para transmitir toda la información operativa y las novedades generadas 
durante el proceso electoral que son necesarias para calcular y ejecutar el pago a cada PA. El objetivo es garantizar que el sistema de liquidación existente de LogiCorp 
reciba de forma estructurada y trazable los datos de presentación, horas trabajadas, suplencias, dobles asignaciones y cualquier novedad que impacte en el monto final 
a liquidar a cada PA

[[página 13]]
Maestro de autoridades de mesa
- Gestionar estados administrativos de autoridades
Gestión del padrón
- Cargar total de electores por elección
- Consultar padrón con filtros avanzados
Notificación DMS
- Generar envíos DMS por lote asociados a elección y autoridad
- Generar envío DMS individual para autoridad
- Soporte a impresión en origen, en nodo, en sucursal destino o por 
organismo gubernamental.
- Imprimir en sucursal destino cuando corresponda
- Usar código de barras del cliente en la pieza/etiqueta
- Configurar modelo de nota personalizable por elección/cliente
- Configurar plantilla con variables y branding básico
- Consultar y exportar estados de envíos
- Visualizar tablero de seguimiento de envíos
Pre-elección
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Gestión de Autoridades de Mesa
Arquitectura e integraciones
Autoridad de 
mesa
Backoffice electoral 
Portal de autogestión (web de pago)
- Login 
- Recuperar contraseña con validación por e-mail (OTP)
- Cargar y actualizar datos personales, domicilio y contacto 
- Cargar y actualizar datos bancarios: CBU, Alias, CUIT/CUIL, titularidad
- Cargar y actualizar datos personales y bancarios de autoridad por terceros autorizados
- Consultar estado de pago
- Visualizar y descargar comprobantes de pago
Pilares del negocio
El modulo de Gestión de Autoridades de Mesa centraliza la administración de todos los actores que participan como autoridades en las mesas de votación: datos personales, 
notificaciones, portal de autogestión y gestión del padrón electoral. Opera el equipo de backoffice de LogiCorp, Voluntarios y Autoridades de mesa
13
Integraciones
- API Índice de Domicilios
- API Alta de envios
- API de seguimiento de envios DMS 
Volunta
rio
Post-escrutinio
prov
Maestro de autoridades 
de mesa
- Auditar historial 
completo de acciones 
sobre autoridades
- Cargar archivo 
CSV/XLSX con 
autoridades y estados 
de pago 
- Cargar manualmente 
comprobantes por PA
Portal de autogestión (web de pago)
- Login 
- Recuperar contraseña con validación por e-mail 
(OTP)
- Buscar y editar datos de autoridad
- Cargar masivamente datos personales, contacto, 
bancarios y domicilio de autoridades de mesa
- Visualizar panel de indicadores: rechazos, 
validaciones fallidas, pagos emitidos y pendientes
- Visualizar auditoría completa de acciones
Elección
Voluntarios
- Registrar voluntario por 
canal presencial
- Gestionar estados de 
elegibilidad 
Voluntarios
- Registrar voluntario

[[página 14]]
Arquitectura e integraciones
Procesos automáticos
14
✓ Modulo Gestión de Autoridades de Mesa
El sistema dentro del modulo debe poder:
Maestro de autoridades de mesa
• Registrar historial completo de acciones sobre cada autoridad
Portal de autogestión (web de pago)
• Validar:
• Validar formato y consistencia de CBU/Alias/CUIT, unicidad por 
persona (Sin validación contra servicio externo)
• OTP de e-mail/teléfono
• Notificar pago rechazado o confirmado a la autoridad de mesa
• Registrar auditoría completa de acciones
Notificación DMS
• Registrar trazabilidad completa de la pieza (admisión, clasificación, tránsito, 
intento de entrega, disponible en sucursal, entregado, no entregado y 
acuse/firma) integrando API de seguimiento de envios DMS de LogiCorp
• Integrar API índice de domicilio en el envío
Voluntarios
• Validar elegibilidad del voluntario contra padrón electoral
• Registrar trazabilidad completa de inscripción del voluntario

[[página 15]]
Arquitectura e integraciones
Integraciones a Desarrollar
Modulo Gestión de PA y TT
✓ API Índice de Domicilios
Obtención de datos de domicilio de Autoridades de mesa
El sistema consume la API del Índice de Domicilios de LogiCorp para validar, normalizar y precisar las direcciones registradas por las autoridades de mesa en el portal 
de autogestión o cargadas masivamente por el backoffice. El objetivo es garantizar que cada domicilio almacenado en el maestro de autoridades sea una dirección 
real, completa y procesable por el sistema logístico DMS
✓ API Alta de envios
Obtención de datos de altas de autoridades de mesa para envios por DMS
El sistema utiliza la API de alta de envíos del servicio DMS de LogiCorp para registrar formalmente cada pieza postal (Telegrama, carta, notas de notificación, etc) 
destinada a una autoridad de mesa, transmitiendo los datos necesarios (código de pieza, etiqueta, código de barras) para que la operación logística pueda procesar, 
imprimir y distribuir la notificación oficial en los canales tradicionales de distribución de LogiCorp asociando cada envío generado a la elección y autoridad 
correspondiente en el maestro interno para garantizar trazabilidad completa
✓ API de seguimiento de envios DMS 
Obtención de seguimiento de envios por DMS
El sistema consume la API de seguimiento del servicio DMS de LogiCorp para obtener en tiempo real el estado de cada pieza postal enviada a las autoridades de 
mesa, actualizando el maestro interno y permitiendo al backoffice y al cliente externo conocer el avance de la distribución sin necesidad de consultar manualmente el 
sistema postal. El objetivo es brindar visibilidad completa del estado de cada notificación a lo largo de toda la cadena logística, desde la admisión hasta la entrega o el 
intento fallido.

[[página 16]]
Módulo de material electoral
- Crear catálogo de tipos de materiales por elección
- Definir árbol de materiales
- Dar de alta masiva de materiales e insumos
- Dar de alta individual de material con identificación unívoca
- Cargar datos logísticos del material (dimensiones, peso, serie/ID)
- Vincular material a contenedor
- Configurar etiquetado flexible por tipo de material y elección
- Configurar ciclos de vida y estados por tipo de material
Pre-elección
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Material electoral y trazabilidad
Arquitectura e integraciones
Coordinador 
de nodo
Ccoordinador 
planificación
Stack 
Tecnológico
Pilares del negocio
El modulo de Material electoral y trazabilidad gestiona el ciclo de vida completo de los materiales electorales: alta, identificación, seguimiento de ubicación, 
auditoría de preparación, armado, expedición y rendición. Operan equipos de coordinación logística, coordinadores de nodo y supervisores.
Integraciones
Módulo de material electoral
- Reimprimir etiqueta con control y auditoría
- Consultar reportes de stock, faltantes, observados y reimpresiones
- Gestionar materiales consumibles y no consumibles
Auditoría de proceso
- Visualizar datos de auditoría durante la preparación (parcial)
- Visualizar datos de auditoría final previa a expedición/entrega
- Escanear y observar artículos parametrizados desde maestro
- Visualizar imagen de referencia del elemento controlado
Supervisor
Auditoría de proceso
- Habilitar tareas por material logístico para materiales críticos
- Consultar informe de avance y desvíos para material observable
Rendición
- Registrar rendición materiales por nodo
- Rendir distintos tipos de materiales y 
documentación
- Cargar incidencias del material rendido
- Recepcionar materiales en centro de 
acopio identificando receptor, timestamp, 
ruta/nodo/TT
- Agrupar por sección u otro criterio 
definido por Tribunal
Post-escrutinio prov
Armado / Finishing
- Configurar por elección qué contiene cada 
material
Armado / Finishing
- Gestionar ingresos de materiales e insumos
- Consultar visibilidad de recibido vs. pendiente con 
fechas límite
- Confirmar recepción en nodo (recibido vs. 
expedido vs. pendiente)
- Distinguir entre productos nomenclados y 
genéricos
Armado / Finishing
- Ejecutar preparación/armado parcial registrando 
avance
- Registrar evidencia fotográfica de stock
- Gestionar retorno de consumibles y no 
consumibles
- Aplicar cambios de materiales, cantidades y 
sustitutos
- Consultar dashboard de recibido, faltante y 
completitud
- Preparar material manualmente por pantalla o 
importación
Rendición
- Configurar reglas específicas de 
rendición por elección/Tribunal electoral
Elección
Armado / Finishing
- Gestionar 
sustitución o 
cambio de 
cantidades de 
materiales en 
campo

[[página 17]]
Arquitectura e integraciones
Procesos automáticos
✓ Modulo Material electoral y trazabilidad
El sistema dentro del modulo debe poder:
Módulo de material electoral
• Registrar seguimiento de ubicación, responsable, timestamp y movimientos
• Generar alertas por inconsistencias de stock o trazabilidad
Auditoría de proceso
• Registrar usuario que realizó cada control con Timestamp
Rendición
• Comparar materiales recibidos contra lo esperado según despliegue
• Validar secuencia y duplicados cuando aplique
• Registrar trazabilidad completa de movimientos y estados

[[página 18]]
Módulo de gestión de tareas y templates
- Crear catálogo de templates con nombre, descripción y tipo
- Configurar workflow/ciclo de vida del template
- Definir metadatos del template: nombre, descripción, tipo de tarea, 
workflow/ciclo de vida con estados y transiciones permitidas
- Definir campos a completar (formulario con obligatorios/opcionales), 
adjuntos obligatorios y si requiere revisión/aprobación posterior
- Definir condiciones operativas (geo, foto, aprobación, etc.)
- Definir ventanas horarias de visibilidad y ejecutabilidad
- Bloquear visibilidad y ejecución de tarea fuera de la ventana horaria 
definida
- Definir reglas de visibilidad por rol y proceso electoral
- Crear nuevos templates
- Asignar tareas por rol, nodo, escuela, mesa o usuario individual
- Definir orden secuencial de tareas
- Definir días y horarios específicos de ejecución
- Controlar estados por plantilla y por tarea
- Configurar reglas de SLA, prioridad, recordatorios y alertas
- Ejecutar rollback o actualizar template ya enviado
Pre-elección
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Aplicación Mobile - Backoffice
Arquitectura e integraciones
Supervisor Backoffice electoral 
Intervención manual de tareas – Contingencia
- Completar o editar manualmente tarea
Pilares del negocio
El modulo de Aplicación Mobile – Backoffice permite la creación, administración y asignación de tareas operativas basadas en plantillas configurables, y soporta 
intervenciones manuales ante contingencias. Opera el equipo interno de coordinación operativa de LogiCorp: Backoffice y supervisión
18
Integraciones
Post-escrutinio prov
Módulo de gestión de tareas y templates
- Revisar histórico de estados de tareas y 
templates
Módulo de gestión de tareas y templates
- Enviar tareas dinámicamente
Elección Apertura de escrutinio prov

[[página 19]]
Arquitectura e integraciones
Procesos automáticos
✓ Modulo Modulo Aplicación Mobile - Backoffice
El sistema dentro del modulo debe poder:
Gestión de tareas y templates
• Gestionar estados de instancia de tarea: asignada, pendiente, en ejecución, 
completada, rechazada, vencida — con historial, usuario responsable y tiempos
• Enviar tareas por push online y cola offline según reglas
Intervención manual de tareas
• Aplicar manejo de permisos y roles para intervenciones

[[página 20]]
Aplicación Mobile para PA y TT
- Login
- Completar módulo de capacitación
- Completar prueba posterior a capacitación
- Practicar en entorno de simulación para capacitaciones 
presenciales
Pre-elección
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Aplicación Mobile - Operación en Campo
Arquitectura e integraciones
Coordinad
or de Nodo TT
Aplicación Mobile para PA y TT
- Visualizar tareas completadas por contingencia con dashboard, 
registro de autor, fecha y esquema de aprobación
Pilares del negocio
El modulo Aplicación Mobile - Operación en Campo proporciona las herramientas digitales para que PA, TT y personal interno de nodo operen en campo durante la 
jornada electoral, incluyendo soporte offline-first y canales alternativos de comunicación.
20
Integraciones
- API de envio telegramas - Juntas 
Electorales
Post-escrutinio prov
Aplicación Mobile para PA y TT
- Ejecutar tarea asignada en la app
- Recibir tareas específicas pusheadas durante elección
- Capturar imagen como evidencia de tarea
- Escanear DNI para toma de datos externos de autoridad
- Verificar si la autoridad ya cargó datos en el portal web
- Crear incidencia y marcar su resolución
- Registrar tarea completada por contingencia
Elección
PA
Digitalización en establecimientos
- Capturar imagen optimizada del telegrama en el establecimiento
- Reintentar captura si la validación de calidad de imagen falla
- Ejecutar flujo específico de comunicación si no se logra calidad 
tras varios intentos
- Transmitir imagen capturada (online u offline)
Digitalización y telegramas en nodos - Banco Digital
- Iniciar digitalización masiva de telegramas al cierre / 
arribo TT
- Visualizar semáforos de calidad por imagen
- Re-escanear telegrama con guía del panel
- Visualizar progreso, faltantes y calidad desde panel 
de escaneo
Digitalización y telegramas en nodos - Banco Digital
- Publicar telegramas de forma controlada para el 
Tribunal
- Consultar histórico de tareas geolocalizadas 
ejecutadas
Operador de 
Nodo

[[página 21]]
Arquitectura e integraciones
Procesos automáticos
✓ Modulo Aplicación Mobile - Operación en Campo
El sistema dentro del modulo debe poder:
Aplicación Mobile para PA y TT
• Registrar visualización de capacitación completada
• Sincronizar automáticamente al recuperar conectividad
• La app detecta conectividad, envía la cola de eventos pendientes al 
servidor y recibe las actualizaciones de tareas.
• Geolocalizar tarea ejecutada
• Controlar y alertar tarea realizada fuera del establecimiento
Digitalización en establecimientos
• Aplicar auto-recorte, centrado y eliminación de bordes
• Validar telegrama capturado por OCR de número y palabras clave
• Avisar en línea si la imagen debe retomarse
• Aplicar protocolo de seguridad para todo el proceso de captura
Digitalización y telegramas en nodos - Banco Digital
• Aplicar formato optimizado para calidad, velocidad y trazabilidad
• Registrar estados de procesamiento de cada telegrama
• Indexar automáticamente por elección, distrito, nodo, centro y mesa
• Aplicar validaciones automáticas de calidad (skew, blur, sombras, recorte, 
contraste, auto-rotación)
• Generar auditoría por hash, timestamp y operador/estación

[[página 22]]
Arquitectura e integraciones
Integraciones a Desarrollar
Aplicación Mobile - Operación en Campo
✓ API de envio telegramas - Juntas Electorales
Telegramas digitalizados — imagen, metadatos, hash de integridad
El sistema transmite los telegramas digitalizados a cada Junta Electoral mediante un cliente de integración configurable por Junta y por 
elección, garantizando la integridad del envío mediante validaciones criptográficas y un mecanismo robusto de reintentos.

[[página 23]]
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Escrutinio Provisorio y Contabilización (IA)
Arquitectura e integraciones
Coordinad
or de Nodo
Integraciones a desarrollar
- API de precarga de resultados para clientes
Pilares del negocio
El modulo Escrutinio Provisorio y Contabilización (IA) esta especializado en la interpretación automatizada de resultados electorales mediante IA, con precarga de 
datos, detección de anomalías y disponibilización de resultados en tiempo real.
23
Integraciones
- API LLM
Post-escrutinio prov
Parseo de votos y disponibilización (IA)
- Visualizar tablero con resultados parciales y mapa geográfico por Elección
- Revisar anomalías detectadas en el tablero de escrutinio provisorio
- Validar y corregir precarga de resultados ante anomalía
Escrutinio prov
Coordinación de Escrutinio 
provisorio
Parseo de votos y disponibilización (IA)
- Exportar resultados consolidados finales
Apertura de escrutinio prov

[[página 24]]
Arquitectura e integraciones
Procesos automáticos
✓ Modulo Escrutinio Provisorio y Contabilización (IA)
El sistema dentro del modulo debe poder:
Parseo de votos y disponibilización (IA)
• Leer automáticamente datos numéricos y marcas en telegramas/actas
• Precargar automáticamente resultados para reducir error humano
• Detectar anomalías matemáticas o patrones sospechosos
• Consolidar resultados parciales en tiempo real
• Aislar datos de cada elección en paralelo sin cruce
• Disponibilizar precarga de resultados por API a clientes

[[página 25]]
Arquitectura e integraciones
Integraciones a Desarrollar
Escrutinio Provisorio y Contabilización (IA)
✓ API de precarga de resultados para clientes
Publicación de datos parciales de resultados electorales
El sistema expone una API que permite a los clientes externos (Juntas Electorales, organismos gubernamentales u otros sistemas autorizados) 
consumir en tiempo real los resultados parciales del escrutinio provisorio a medida que son procesados e interpretados por el módulo de IA. El 
objetivo es reducir los tiempos de disponibilización de datos eliminando la intermediación manual y garantizando el aislamiento entre 
elecciones simultáneas.
✓ API LLM
Parseo de votos mediante IA durante el escrutinio provisorio de telegramas
El sistema utiliza una API de modelo de lenguaje de gran escala (LLM) combinada con capacidades de OCR para interpretar el contenido de 
los telegramas electorales digitalizados, extrayendo automáticamente los datos numéricos de votos, marcas y firmas de cada acta. El objetivo 
es reducir drásticamente el tiempo y el error humano en el proceso de escrutinio provisorio, permitiendo que los resultados de cada mesa estén 
disponibles en el sistema en minutos desde la recepción del telegrama digitalizado, sin requerir carga manual por parte de operadores. El LLM 
actúa como capa de interpretación inteligente sobre los resultados del OCR, resolviendo ambigüedades en la lectura (números tachados, 
escritura ilegible, campos incompletos) y detectando inconsistencias matemáticas antes de que los datos sean cargados al sistema.

[[página 26]]
Mesa de soporte y monitoreo
- Configurar workflows de tratamiento de tickets
- Gestionar reglas de alertas y prioridades
Pre-elección
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Mesa de Soporte y Monitoreo
Arquitectura e integraciones
Operador Mesa de Soporte Backoffice electoral 
Integraciones a desarrollar
- API envio documentación a Tribunal electoral
Pilares del negocio
El modulo Mesa de Soporte y Monitoreo permite operar como Centro operativo centralizado para la gestión de incidencias durante la jornada electoral, con 
monitoreo en tiempo real, gestión de tickets, alertas automáticas y comunicación con el Tribunal Electoral.
26
Integraciones
Post-escrutinio prov
Mesa de soporte y monitoreo
- Visualizar en tiempo real estado de nodos, rutas, centros, mesas y materiales
- Crear ticket de incidencia manualmente
- Asignar ticket a responsable
- Disparar tarea correctiva móvil desde un ticket
- Crear tarea manual en tiempo real
- Resolver y cerrar ticket de incidencia
- Monitorear KPIs de incidentes, tiempos de respuesta y volumen de tareas
- Consultar histórico de tickets, acciones y tiempos de resolución
- Generar reporte operativo diario y post-elección
- Enviar documentación al Tribunal Electoral
Elección Apertura de escrutinio prov Escrutinio prov

[[página 27]]
Arquitectura e integraciones
Procesos automáticos
✓ Modulo Mesa de Soporte y Monitoreo
El sistema dentro del modulo debe poder:
Mesa de soporte y monitoreo
• Generar alertas automáticas por eventos críticos
• Crear ticket automáticamente ante alerta crítica
• Priorizar automáticamente ticket por reglas configuradas
• Reflejar tickets y resoluciones en apps móviles (integración bidireccional)
• Crear tarea automáticamente en tiempo real
• Enviar notificaciones push por rol, nodo, zona, dispositivo o elección

[[página 28]]
Arquitectura e integraciones
Integraciones a Desarrollar
Escrutinio Provisorio y Contabilización (IA)
✓ API envio documentación a Tribunal electoral
Envio de documentos relacionados a incidencias reportadas durante el acto electoral
El sistema expone una API que permite a los clientes externos (Juntas Electorales, organismos gubernamentales, etc) consumir en tiempo real 
los documentos relacionados a tickets de incidencias generadas durante el acto eleccionario.

[[página 29]]
Tableros en tiempo real (Dashboards)
- Visualización de tableros relevantes por rol (interno o externo) en tiempo real basada en eventos
- Aplicar filtros por elección, zona, nodo y estado en tableros
Pre-elección
Plataforma de Gestión Integral de Operaciones Electorales – Modulo Transversales
Arquitectura e integraciones
Administrador del sistema Todos los usuarios
Integraciones a desarrollar
- API de envio telegramas - Juntas 
Electorales
Pilares del negocio
El modulo Transversales comprende a los componentes que aplican horizontalmente a todos los módulos de la plataforma: dashboards en tiempo real, seguridad y 
roles, soporte multielección, entornos de prueba y transmisión de telegramas.
29
Integraciones
Post-escrutinio
prov
Seguridad y roles
- Crear y administrar roles funcionales
- Definir tareas y permisos por rol
- Configurar aprobaciones escalables para acciones sensibles
- Gestionar usuarios por tipo (LogiCorp, TT, colaboradores)
Multielección
- Configurar nueva elección como red independiente
- Configurar unidades operativas, maestros, calendarios, parámetros, 
etiquetas y visualización por elección
- Visualizar dashboards y métricas particulares por elección
Entornos de prueba
- Configurar entorno aislado para simular proceso electoral completo
- Configurar parámetros, calendarios y particularidades por proceso 
electoral
Transmisión y procesamiento de telegramas
- Configurar cliente de integración por Junta Electoral y elección
- Gestionar versiones de endpoints y contratos por Junta
Elección Apertura de escrutinio prov Escrutinio prov
Transmisión y 
procesamiento de 
telegramas
- Reenviar telegrama 
ante solicitud del 
cliente
Backoffice
electoral

[[página 30]]
Arquitectura e integraciones
Procesos automáticos
✓ Modulo Transversales
El sistema dentro del modulo debe poder:
Tableros en tiempo real (Dashboards)
• Actualizar tableros en tiempo real basados en eventos
• Registrar trazabilidad de fuente del evento, timestamp y usuario/máquina
Transmisión y procesamiento de telegramas
• Validar integridad antes y después del envío (hash, checksum, tamaño, esquema)
• Validar firma del telegrama si fuera requerida,
• Gestionar cola de envíos con reintentos e idempotencia
• Registrar acuse de recibo y evidencia de envío
• Monitorear y alertar ante fallas o discrepancias de integridad
• Registrar bitácora de auditoría completa de transmisiones

[[página 31]]
Arquitectura e integraciones
Consideraciones generales sobre alcance
A continuación se detallan las consideraciones sobre algunos de los apartados del documento 
DMS Elecciones.
5.2.1 — Reclutamiento de Personal: Bot de WhatsApp
Alcance incluido en la propuesta: Se implementará un bot de WhatsApp mediante la 
plataforma Twilio para cubrir la interacción inicial con candidatos PA, incluyendo validación de 
datos, screening automatizado y confirmación de disponibilidad. TechPartner implementa y 
configura la integración técnica con Twilio. LogiCorp es responsable de configurar los flujos, 
árboles de decisión y mensajes del chatbot directamente en la UI de Twilio. El desarrollo de 
los flujos conversacionales queda fuera del alcance de TechPartner.
⚠️ Dependencia: El inicio del desarrollo de esta integración está condicionado a que LogiCorp 
tenga activa y configurada una cuenta Twilio con acceso a WhatsApp Business API.
________________________________________
5.1.2 y 5.2.3 — Optimizador de recorridos y asignación geolocalizada: Motor de mapas
Alcance incluido en la propuesta: Los módulos de optimización de flota y recorridos (5.1.2) y 
de asignación geolocalizada de PA (5.2.3) requieren un motor externo de mapas y cálculo de 
tiempo de viaje. TechPartner utilizará Google OR-Tools para la optimización combinatoria de 
rutas y Google Maps APIs para geolocalización, cálculo de distancias y tiempos de viaje. El 
costo de las APIs de Google es a cargo de LogiCorp
⚠️ Dependencia: LogiCorp deberá proveer las credenciales y la cuenta de facturación de 
Google Cloud Platform antes del inicio del desarrollo de estos módulos.
________________________________________
5.2.2 — Motor de IA para asignación automática de PA
Alcance incluido en la propuesta: El motor de asignación automática de PA se 
implementará como un componente configurable que evaluará y ponderará variables definidas 
por LogiCorp durante el relevamiento funcional. El modelo de scoring a aplicar seguirá el 
esquema: Cumple = 2 puntos / Cumple parcialmente = 1 punto / No cumple = 0 puntos. Los 
parámetros de evaluación, sus ponderaciones y las variables excluyentes serán configurables 
desde el backoffice por el área de RRHH, sin necesidad de intervención técnica. Los datos de 
entrada del motor serán los cargados en la plataforma, ya sea por autogestión del PA o por 
carga de RRHH.
⚠️ Indefinición funcional: Las variables específicas a evaluar, sus ponderaciones relativas y 
los criterios excluyentes no han sido definidos al momento de esta propuesta. Su definición es 
condición necesaria para completar el diseño e implementación del motor. TechPartner incluye 
en su estimación el desarrollo del motor configurable, pero el diseño de las reglas de negocio 
queda sujeto a una sesión de relevamiento funcional específica con LogiCorp antes del inicio 
de la fase correspondiente.
5.3.3 — Notificación
Alcance incluido en la propuesta: Las altas de envíos DMS se realizarán vía API del servicio 
DMS actual de LogiCorp. Con la información del response de esa API se generarán las 
notas o formularios a imprimir. La impresión de las piezas se realizará de forma manual 
por el equipo de LogiCorp. La distribución física también se realizará de forma manual a 
través de la logística de LogiCorp.

[[página 32]]
Arquitectura e integraciones
Consideraciones generales sobre alcance
A continuación se detallan las consideraciones sobre algunos de los apartados del documento DMS 
Elecciones.
5.2.9 — Gestión administrativa de PA: Pagos y materiales
Alcance incluido en la propuesta:
• Confirmación de pagos desde nodos: El registro de confirmación de pago (fecha, monto, 
medio de pago y usuario responsable) se realizará mediante ingreso manual en pantalla. No se 
consulta ningún servicio externo ni se consume ningún archivo.
• El sistema se integrará vía API con el módulo Oracle HCM para la liquidación de pagos al 
Personal de Apoyo. La plataforma transmitirá al HCM de Oracle toda la información y novedades 
necesarias para el cálculo y liquidación de los pagos correspondientes a la jornada electoral, 
incluyendo presentación efectiva, horas trabajadas, suplencias, dobles asignaciones y bajas por 
no presentación. El cálculo final de los haberes y la ejecución del pago quedan bajo 
responsabilidad del HCM de Oracle
• Gestión de medios de pago alternativos: El registro y seguimiento de medios de pago 
alternativos, incluyendo excepciones y trazabilidad de cambios, se realizará mediante ingreso 
manual en pantalla. No se consulta ningún servicio externo ni se consume ningún 
archivo.
• Seguimiento del estado de pago: Los estados de pago (pendiente, en proceso, aprobado, 
pagado, rechazado) se gestionarán mediante la carga manual de un archivo CSV o XLSX 
que contiene las autoridades de mesa y el estado de sus pagos. El sistema leerá este 
archivo, validará los estados y enviará las alertas correspondientes ante demoras o 
inconsistencias. No existe integración con ningún sistema de pago externo.
________________________________________
5.3.6 — Portal de autogestión (web de pago): Login de Autoridades de Mesa
Alcance incluido en la propuesta: Las autoridades de mesa podrán ingresar al portal utilizando 
su e-mail y número de DNI, ambos incluidos en el archivo de autoridades de mesa provisto por 
Junta Electoral cargados en la Plataforma via importación por usuario LogiCorp. Una vez validados 
estos datos contra el archivo, la autoridad de mesa podrá generar su propio usuario y contraseña 
para accesos posteriores. No se implementará un sistema de identidad externo (SSO, OAuth social) 
en esta versión para las autoridades de mesa
________________________________________
5.3.7 — Integración de medios de pago en portal de autogestión
Fuera de alcance de esta propuesta. La integración del portal de autogestión con medios de pago 
externos queda explícitamente excluida del presente relevamiento y estimación. 
________________________________________
5.9.4 — Entornos de prueba: Envíos en ambiente QA
Alcance incluido en la propuesta: Las pruebas de envío de telegramas en ambiente QA quedarán 
incorporadas dentro del plan de casos de prueba de QA del proyecto. No constituyen un 
entregable separado sino parte integral del proceso de testing de integración con las Juntas 
Electorales.

[[página 33]]
Arquitectura e integraciones
Consideraciones generales sobre alcance
A continuación se detallan las consideraciones sobre algunos de los apartados del documento 
DMS Elecciones.
5.6.2 — Canales alternativos: WhatsApp y SMS
Alcance incluido en la propuesta: Ante falla de la app mobile por problemas de 
conectividad o del dispositivo, el PA podrá enviar la información operativa al centro de control 
mediante WhatsApp o SMS. El personal del backoffice recibirá estos mensajes y registrará 
los datos manualmente en el sistema, sin integración técnica con ningún servicio externo 
de mensajería en esta dirección.
⚠️ Riesgo identificado: Este mecanismo introduce un vector potencial de fraude o error, dado 
que la información ingresada al sistema por el backoffice no proviene directamente del 
dispositivo del PA sino de un mensaje de texto no autenticado criptográficamente. Se 
recomienda que LogiCorp defina, antes del inicio del desarrollo, los controles operativos y de 
auditoría que mitiguen este riesgo: por ejemplo, validación cruzada con datos de 
geolocalización previos, esquema de doble confirmación por supervisor, o restricción del canal 
alternativo a un conjunto acotado de tipos de tarea de bajo riesgo.
Exclusiones explícitas adicionales de esta propuesta:
• Gestión de pasajes y hospedaje para personal interno (excluido en sección 5.2.7 del pliego)
Dependencias críticas que condicionan el inicio de las distintas fases del proyecto:
• Definición de variables, ponderaciones y criterios excluyentes del motor de IA — condiciona 
módulo 5.2.2
• Resolución sobre template DMS (propio) y tipo de documento (formulario vs. telegrama) —
condiciona módulo 5.3.3
• Provisión del archivo de autoridades de mesa con e-mail y DNI para pruebas — condiciona 
módulo 5.3.6
• Definición de controles anti-fraude para canal alternativo WhatsApp/SMS — condiciona 
módulo 5.6.2
Suposiciones realizadas
• El proceso de alta en AFIP cuenta con una API ya existente al que se integrará, no un 
desarrollo nuevo
• Se asume que la app mobile será en React Native, se generarán blundes para Android & 
IOS
• Las APIs de las Juntas Electorales (Envio de telegramas y documentación) son provistas 
por el LogiCorp junto con documentación técnica y ambiente de prueba. 
• La API índice de domicilios, API liquidación de pagos a transportistas, API liquidación de 
pagos a PA, API Alta de envios y API de seguimiento de envios DMS son una integraciones 
de LogiCorp disponible existente que será provista con documentación técnica y ambiente 
de prueba
• Los diseños en Figma mencionados en la sección 6 (Entregables de diseño y validación) 
serán provistos antes del inicio del desarrollo de cada módulo. 
• El archivo de autoridades de mesa provisto por la Junta Electoral para el login del portal 
(5.3.6) contendrá al menos e-mail y DNI validados por elección

[[página 34]]
Arquitectura e integraciones
Consideraciones sobre APIs de LLM
Módulos involucrados: 5.1.2 Optimizador de flota y recorridos / 5.2.2 Asignación automática de 
PA / 5.7.1 Parse de votos y disponibilización
Proveedor y modelo
No se ha definido el proveedor de LLM a utilizar (OpenAI, Anthropic, Google Gemini, Azure 
OpenAI u otro), ni la versión del modelo. Esta decisión impacta directamente en los costos 
operativos, la latencia de las respuestas, la disponibilidad del servicio y las condiciones de 
privacidad de datos aplicables. Deberá resolverse antes del inicio del diseño de arquitectura de 
los módulos correspondientes.
Costos operativos
El costo de consumo de la API de LLM es variable y depende del volumen de tokens procesados 
por cada consulta. LogiCorp asume el costo operativo de la API
Privacidad y confidencialidad
APIs de LLM de terceros procesan los datos enviados en cada prompt en servidores externos. 
En el caso del módulo de asignación de PA, los prompts contendrían datos personales de 
candidatos (domicilio, disponibilidad, características del celular, doble rol). Deberá evaluarse si 
esto es compatible con la política de privacidad de datos de LogiCorp y con la normativa 
aplicable sobre Protección de Datos Personales.
Disponibilidad y latencia
Los módulos que consumen LLM dependen de la disponibilidad de un servicio externo. Una 
caída o degradación del proveedor de LLM durante la semana de elección podría bloquear 
la ejecución del optimizador de flota o impedir la generación de propuestas de asignación 
de PA.
Determinismo y reproducibilidad
Los modelos de lenguaje son no deterministas por naturaleza: ante el mismo input pueden 
generar outputs distintos en cada ejecución. En el contexto de asignación de PA o de 
optimización de flota, esto puede generar inconsistencias difíciles de auditar. 
Validación humana obligatoria
Alcance incluido en la propuesta: Toda recomendación generada por el LLM — tanto en 
optimización de flota como en asignación de PA — deberá ser revisada y confirmada por un 
operador humano antes de aplicarse al sistema. El LLM actúa como asistente de decisión, no 
como decisor autónomo. 
Prompt engineering y mantenimiento
La calidad de las respuestas del LLM depende fuertemente del diseño de los prompts. Prompts
mal diseñados pueden generar recomendaciones incorrectas, incompletas o con alucinaciones. 
TechPartner asume la responsabilidad del diseño inicial de los prompts para ambos módulos, 
pero deberá establecerse un proceso formal de revisión y ajuste de prompts durante las fases de 
QA
Restricción de alcance
Alcance incluido en la propuesta: El uso de LLM en esta propuesta se limita exclusivamente 
a los dos módulos identificados: asistencia al optimizador de flota y recorridos (5.1.2), 
motor de asignación de PA (5.2.2) y Parseo de votos y disponibilización (5.7.1). Cualquier 
extensión del uso de LLM a otros módulos de la plataforma requerirá una definición funcional 
específica y una nueva estimación de esfuerzo y costo operativo.
