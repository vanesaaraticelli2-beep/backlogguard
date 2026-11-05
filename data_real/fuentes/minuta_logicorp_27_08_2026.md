---
source_name: Minuta LogiCorp 27-08-2026
source_type: minuta
source_date: '2026-08-27'
layout: dialogo
fingerprint: c62b118ca534f157
---
Nota de la minuta: Minuta de reunión
Nota de la minuta: Objetivo de la reunión
Nota de la minuta: Definición de tareas y templates en el Backoffice, inputs y acciones de la app móvil, y lógica de validación local y offline de escaneo de DNI de las autoridades de mesa
Nota de la minuta: Fecha – 27-08-2026
Nota de la minuta: Hora – 14.10
Nota de la minuta: Lugar – Teams
Nota de la minuta: Modalidad – Virtual
Nota de la minuta: Convocada por – Persona 1
Nota de la minuta: Convocados a la reunión
Nota de la minuta: Persona 4 (LogiCorp) Persona 1 (TechPartner) Persona 2 (TechPartner)
Nota de la minuta: Detalle de temas tratados
Nota de la minuta: Tema #1: Concepto, Configuración y Categorías de Tareas en la App Móvil
Nota de la minuta: Una "tarea" representa una actividad o hito macro que el Personal de LogiCorp (PA) debe cumplir en el establecimiento de votación el día domingo (ej. "Presente en el colegio" o "Entrega de urna").
Nota de la minuta: Cada tarea se compone internamente de pasos o acciones secuenciales obligatorias (ej. escanear DNI de escuela, sacar foto de fachada).
Nota de la minuta: Bloqueo y Dependencia Temporal: Es fundamental restringir/bloquear la ejecución de tareas según dependencias o franjas horarias específicas, forzando a hacerlas únicamente en el momento oportuno. En experiencias anteriores, los operadores que reciben múltiples tareas se ponen ansiosos e intentan completar hitos de la tarde o cierre al mediodía para retirarse antes, registrando los datos de manera incorrecta. El sistema debe bloquear hitos futuros hasta que se cumplan las dependencias o el horario establecido.
Nota de la minuta: Categorización y Roles:
Nota de la minuta: Se contemplan categorías para organizar las tareas, tales como "Transporte", "Digitalización" y "Supervisión". Persona 4 cuestiona la categoría "Supervisión", pero se acuerda mantener la categorización para facilitar el filtrado a la hora de asignar tareas a usuarios o visualizar métricas de control.
Nota de la minuta: La parametrización de nuevas categorías debe resolverse con una interfaz simple: un botón de "Agregar nueva" dentro de la propia lista desplegable de la UI, permitiendo escribir y registrar una nueva categoría sobre la marcha sin derivar a pantallas de configuración externas.
Nota de la minuta: En el MVP, el selector de roles se mantendrá por motivos de escalabilidad futura, pero las tareas del domingo se limitarán de forma operativa al Personal de LogiCorp (PA), quedando el rol de Transportistas excluido de este alcance.
Nota de la minuta: Restricción de Permisos: La creación y edición de tareas en el Backoffice se limitará a un rol jerárquico superior (Super Admin o Analistas designados oportunamente por el rol asignado), ya que un administrador local o de nodo no debe manipular la estructura global de las tareas.
Nota de la minuta: Tema #2: Análisis de la UI de Figma y Especificación de Campos
Nota de la minuta: En las pantallas de Figma se observa un panel lateral desplegable (side drawer) con switches generales para cada acción (ej. "Módulo activo", "Pasos visibles en cabecera", "Barra de progreso").
Nota de la minuta: Persona 4 advierte que algunas secciones visuales del Figma "quedaron más flojas" o se repiten de forma inconsistente en varias pantallas (como replicar configuraciones idénticas en tareas y en templates).
Nota de la minuta: Tema #3: Escaneo y Validación de DNI (Offline y Online)
Nota de la minuta: Mapeo Automático: Al escanear el DNI, la app móvil debe extraer los datos (Nombre, Apellido y DNI) y autocompletar la información de forma inmediata, habilitando un campo editable por si el OCR comete errores. La app móvil debe funcionar idénticamente con o sin conexión de red (offline/online) para el análisis del DNI debe realizarse de forma local en el dispositivo; la sincronización de tareas se realizará en segundo plano una vez captada la señal
Nota de la minuta: Debate sobre el Algoritmo Técnico:
Nota de la minuta: Se menciona que Persona 5 (líder técnico de LogiCorp) implementó la validación local de DNI en la aplicación anterior, la cual está obsoleta. Persona 4 advierte que el algoritmo anterior de Persona 5 no es el mejor porque genera muchos falsos positivos y errores de procesamiento: se detectaron problemas de codificación al parsear caracteres especiales como tildes, la letra "Ñ" y nombres compuestos, mezclándolos o trabando la app.
Nota de la minuta: Se acuerda que TechPartner analizará con Persona 5 este desarrollo para proponer un mecanismo robusto y optimizado para el MVP.
Nota de la minuta: Tratamiento de Extranjeros: Cualquier ciudadano en el padrón electoral puede actuar como presidente de mesa. En el caso de extranjeros nacionalizados con DNI argentino válido, el formato no varía del nativo, descartándose del alcance DNIs extranjeros sin validez electoral argentina.
Nota de la minuta: Tema #4: Jerarquía Metodológica de Tareas vs. Templates de Tareas
Nota de la minuta: El Figma presenta pantallas que repiten la configuración detallada de acciones (inputs de datos) tanto al crear una tarea como al crear un template.
Nota de la minuta: La jerarquía unificada: Persona 4 aclara que la lógica operativa correcta es estructurar los desarrollos separando ambas entidades:
Nota de la minuta: Template (Plantilla): Define la estructura técnica atómica de la actividad, es decir, el formulario y el conjunto de campos o acciones requeridas (ej. "Confirmar Asistencia" o "Entrega de Urna").
Nota de la minuta: Tarea: Representa la instancia de ejecución a nivel de elección que asocia un template único heredando su formulario. La tarea contiene la lógica de negocio secundaria como la asignación, los ruteos y el despacho a los operadores.
Nota de la minuta: Ejemplo Práctico de Confirmación de Asistencia: El template es "Confirmar Asistencia". El operador de backoffice crea dos tareas de ejecución a partir del template “Confirmar asistencia”: "Asistencia de la Mañana" y "Asistencia de la Tarde". Ambas tareas se clonan utilizando el mismo template reutilizable de asistencia, simplificando la administración y evitando duplicar pantallas.
Nota de la minuta: Modelo de Ámbitos (Scopes):
Nota de la minuta: Para resolver el riesgo de que la configuración de una elección en curso sea alterada accidentalmente por otro planificador que prepara un comicio concurrente (ej. Chaco que opera un domingo y Corrientes el domingo siguiente), Persona 1 propone y se acuerda implementar un modelo de ámbitos o scopes:
Nota de la minuta: Scope Global (Repositorio de Templates): Contiene las plantillas estáticas y reutilizables del sistema, las cuales solamente pueden ser editadas por un usuario con rol autorizado.
Nota de la minuta: Scope Local (Tareas de la Elección): Al configurar una elección, el usuario busca un template genérico en el repositorio global y lo clona/duplica localmente a su elección. De este modo, cualquier ajuste menor (ej. modificar textos de roles locales o agregar un campo de foto específico para Chaco) se realiza dentro de la tarea en el scope local de esa elección, blindando los templates globales y asegurando el aislamiento entre elecciones concurrentes.
Nota de la minuta: Acuerdos de la reunión
Nota de la minuta: Acuerdo #1: Las tareas móviles de la aplicación del domingo se enfocarán en el rol de Personal de LogiCorp (PA), manteniendo el selector de Transportista de manera simulada por escalabilidad pero excluyendo sus pantallas del MVP. Acuerdo #2: Se implementará una restricción jerárquica de accesos en el Backoffice, de modo que la creación y edición de tareas esté limitada a un rol administrador superior (Super Admin / Analistas del con rol asignado correspondiente), bloqueando el acceso a perfiles no autorizados. Acuerdo #3: La parametrización de nuevas categorías de tareas se realizará mediante una interfaz simplificada, integrando un botón de "Agregar nueva" directamente sobre la lista desplegable de la grilla. Acuerdo #4: Para evitar sobrecomplejizar el desarrollo inicial del backoffice, se adoptará la premisa de simplificación, priorizando campos de entrada estándar (texto corto, texto largo y numérico) sobre validaciones complejas de audios o videos en este MVP. Acuerdo #5: El escaneo de DNI y autocompletado en la aplicación móvil debe ser completamente funcional en modalidad local y offline, guardando los datos en el dispositivo y sincronizándolos automáticamente en segundo plano al recuperar señal de red. Acuerdo #6: Se unifica la estructura metodológica del backoffice: el Template actúa como la plantilla técnica del formulario y acciones; la Tarea actúa como la instancia operativa local interna a cada elección que se clona desde un template único e implementa la lógica de asignación y envío a los operadores. Acuerdo #7: Se adopta el modelo de aislamiento de ámbitos (Scope Global vs. Local), donde el planificador clona un template global al entorno de su elección para poder adaptarlo libremente sin afectar el repositorio central ni alterar otras elecciones activas concurrentes.
Nota de la minuta: Próximos pasos
Nota de la minuta: Actividades – Analizar con Persona 5 el algoritmo de escaneo offline de DNI; Fecha comprometida – A definir; Responsable – TechPartner
Nota de la minuta: Actividades – Revisar con el equipo de UX para corregir los layouts repetidos o inconsistentes que presentan las pantallas de Figma en el módulo de tareas vs template de tareas; Fecha comprometida – A definir; Responsable – LogiCorp
Nota de la minuta: Trazabilidad
Nota de la minuta: Autor del documento – Persona 1
Nota de la minuta: Fecha de creación – 27/08/2026
Nota de la minuta: Versión – 0
