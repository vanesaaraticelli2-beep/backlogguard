# Auditoría de vínculos con la preventa

- Vínculos revisados: 59 · confirmados: 24 · a descartar: 35 · sin verificar: 0

## RQ-001 (requisito) ✘✔✘ — Elecciones como entidades aisladas e independientes
- C-012: **distinto** · C-012 es un título general de alcance («Soporte multielección y entornos de prueba»), no una funcionalidad concreta.
- C-266: **mismo** · Ambos piden configurar cada elección como entidad o red independiente dentro de Multielección.
- C-267: **distinto** · C-267 trata la configuración de maestros, calendarios y parámetros por elección. El requisito pide aislamiento de datos entre elecciones. Solo comparten el tema multielección.

## RQ-002 (requisito) ✘✘✘✘ — Perfiles Super Admin y Admin por elección
- C-011: **distinto** · C-011 es un título general transversal (dashboards, seguridad, roles, auditoría).
- C-262: **distinto** · C-262 es el mecanismo genérico de roles. El requisito define perfiles específicos (Super Admin / Admin) ligados a la multielección.
- C-263: **distinto** · C-263 es el mecanismo genérico de permisos por rol. No define los perfiles Super Admin/Admin.
- C-268: **distinto** · C-268 ofrece dashboards particulares por elección. El requisito pide perfiles, uno de ellos con vista consolidada de todas las elecciones. Solo comparten el tema.

## RQ-003 (requisito) ✘✘✘ — Permisos de creación y visualización de elecciones por perfil
- C-262: **distinto** · Mecanismo genérico de roles frente a una regla específica de visibilidad y creación de elecciones por perfil.
- C-263: **distinto** · Mecanismo genérico de permisos frente a una regla concreta de alcance por elección creada.
- C-266: **distinto** · C-266 trata la configuración de una elección. El requisito trata permisos de visualización y creación por perfil.

## RQ-004 (requisito) ✔ — Carga masiva de Carta Marina solo con Excel
- C-014: **mismo** · difiere: propuesta: importación masiva sin formato especificado; reunión: exclusivamente archivo Excel · Ambos refieren a la carga masiva del maestro de ubicaciones (Carta Marina / nodos) en el mismo módulo.

## RQ-005 (requisito) ✔ — Carga masiva de Carta Marina con reemplazo total por elección
- C-014: **mismo** · difiere: propuesta: importación masiva sin modo definido; reunión: cada carga borra y reemplaza todos los datos de la elección · Misma funcionalidad de importación masiva del maestro, con un detalle de comportamiento.

## RQ-006 (requisito) ✔ — Edición individual de campos de Carta Marina desde la grilla
- C-013: **mismo** · difiere: propuesta: crear/editar/eliminar registros; reunión: edición campo a campo desde la grilla con ícono de lápiz · Misma funcionalidad de edición de registros del maestro en el mismo módulo.

## RQ-007 (requisito) ✘✘ — Cruce de presentismo y autogestión con órdenes de pago autorizadas
- C-100: **distinto** · C-100 es la consulta de estado de pago en el portal. El requisito es el cruce de presentismo con órdenes de pago para determinar a quién se paga.
- C-110: **distinto** · C-110 notifica el resultado del pago. No realiza el cruce con órdenes autorizadas.

## RQ-008 (requisito) ✘ — Notificar en pantalla la fila del Excel con duplicidad
- C-032: **distinto** · C-032 es genérico (reglas de validación). El requisito pide un comportamiento concreto de presentación del error en pantalla.

## RQ-009 (requisito) ✔✘ — Bloquear importación de Carta Marina ante combinaciones duplicadas de Escuela y Mesa
- C-032: **mismo** · difiere: propuesta: reglas de validación genéricas al importar; reunión: bloqueo por duplicado de ID Escuela + Código de Mesa · Es una regla de validación en la importación del mismo módulo de maestro.
- C-014: **distinto** · C-014 es la importación en sí. La regla de bloqueo por duplicados corresponde a la validación (C-032).

## RQ-010 (requisito) ✘✘ — DNI obligatorio y único en el maestro de autoridades
- C-004: **distinto** · C-004 es un título general de alcance.
- C-084: **distinto** · C-084 gestiona estados administrativos. El requisito trata la unicidad y obligatoriedad del DNI.

## RQ-011 (requisito) ✘✘ — Sin otros campos obligatorios en el maestro de autoridades
- C-004: **distinto** · C-004 es un título general del alcance y no trata campos obligatorios del maestro de autoridades.
- C-084: **distinto** · Gestionar estados administrativos no es definir campos obligatorios del maestro; solo comparten el módulo.

## RQ-012 (requisito) ✘✘ — Roles de autoridades configurables por elección
- C-004: **distinto** · C-004 es un título general del alcance, sin funcionalidad concreta de roles de autoridades.
- C-267: **distinto** · C-267 es una configuración genérica por elección (maestros, parámetros, etiquetas) y no se compromete con un panel de creación de roles de autoridades.

## RQ-013 (requisito) ✔✔✔ — Integración por API con el TMS de LogiCorp para el seguimiento de notificaciones
- C-095: **mismo** · difiere: propuesta: API de seguimiento de envíos DMS; reunión: integración directa por API con el TMS de LogiCorp en lugar de archivos de tracking · Ambos piden integrar por API el seguimiento de envíos de notificaciones con LogiCorp.
- C-113: **mismo** · difiere: propuesta: API de seguimiento DMS de LogiCorp; reunión: API del TMS de LogiCorp · Ambos piden integrar la API de seguimiento de LogiCorp para la trazabilidad de las notificaciones a autoridades.
- C-119: **mismo** · difiere: propuesta: API de seguimiento DMS; reunión: API del TMS de LogiCorp · Ambos piden consumir la API de seguimiento de LogiCorp para obtener el estado de las notificaciones.

## RQ-014 (requisito) ✔✘✘ — Consultar estado de notificación en el TMS por DNI y Número de Contrato
- C-119: **mismo** · difiere: propuesta: estado por pieza postal; reunión: consulta por DNI y Número de Contrato que devuelve número de envío y estado · Ambos piden consultar la API de seguimiento de LogiCorp para obtener el estado de cada notificación.
- C-093: **distinto** · C-093 es la consulta y exportación de estados por el usuario, no la consulta del sistema al TMS por DNI y contrato.
- C-112: **distinto** · Registrar la trazabilidad de la pieza no es consultar al TMS con claves DNI y contrato.

## RQ-015 (requisito) ✔✘ — Actualización automática del estado de notificaciones dos veces al día
- C-119: **mismo** · difiere: propuesta: estado obtenido en tiempo real; reunión: actualización automática dos veces al día · Ambos piden obtener automáticamente el estado de las notificaciones desde la API de LogiCorp.
- C-094: **distinto** · El tablero de seguimiento es visualización, no la actualización automática periódica de estados.

## RQ-016 (requisito) ✘✘✔✘ — Historial cronológico de estados de hasta 3 notificaciones por DNI
- C-093: **distinto** · Consultar y exportar estados es genérico y no es un historial cronológico por DNI.
- C-094: **distinto** · El tablero de seguimiento no es el historial cronológico de estados por DNI.
- C-112: **mismo** · difiere: propuesta: trazabilidad completa de la pieza; reunión: historial de estados de hasta 3 notificaciones por DNI · La trazabilidad completa de la pieza equivale al historial cronológico de estados de la notificación.
- C-119: **distinto** · C-119 trata la obtención del estado vía API, no la visualización del historial por DNI.

## RQ-017 (requisito) ✘✘ — Importación progresiva de autoridades por lotes aislados
- C-085: **distinto** · Cargar el total de electores no es la importación de autoridades por lotes aislados.
- C-087: **distinto** · Solo comparten la palabra 'lote': C-087 genera envíos DMS y es de otro módulo, no la importación de autoridades.

## RQ-018 (requisito) ✘✔ — El sistema no calcula montos ni viáticos; el monto es informativo y lo provee el tribunal
- C-100: **distinto** · Consultar el estado de pago en el portal no trata el cálculo de montos ni viáticos.
- C-300: **mismo** · difiere: propuesta: el cálculo y el pago quedan a cargo de Oracle HCM; reunión: el monto es informativo y lo provee el tribunal · Ambos excluyen que el sistema calcule los montos a pagar a las autoridades.

## RQ-019 (requisito) ✔✔✘ — Carga masiva por Excel de órdenes de pago del tribunal con mapeo dinámico por elección
- C-059: **mismo** · difiere: propuesta: importar CSV/XLSX con estados de pago; reunión: carga masiva por Excel de órdenes de pago del tribunal con mapeo dinámico de campos por elección · Ambos son la importación de un archivo de pagos en el módulo de pagos a PA; la reunión agrega el mapeo dinámico por elección.
- C-302: **mismo** · difiere: propuesta: carga manual de CSV/XLSX para gestionar estados de pago; reunión: carga masiva de órdenes de pago por Excel con mapeo dinámico por elección · Es la misma carga de archivo de pagos de la gestión administrativa de PA, con un detalle distinto de mapeo y contenido.
- C-100: **distinto** · Consultar el estado de pago es una función del portal de autogestión, no la carga masiva de órdenes en el backoffice.

## RQ-020 (requisito) ✘ — Carga masiva de comprobantes de pago en PDF desde archivo ZIP
- C-101: **distinto** · El requisito es subir comprobantes en un ZIP desde el backoffice; el compromiso es que la autoridad los vea y descargue en el portal.

## RQ-021 (requisito) ✔✘ — Condicionar la notificación de pago a que el comprobante esté cargado y asociado
- C-110: **mismo** · difiere: propuesta: notificar pago rechazado o confirmado; reunión: notificar solo si el comprobante ya está cargado y asociado · Es la misma notificación de pago a la autoridad de mesa; la reunión le agrega una condición.
- C-101: **distinto** · La visualización de comprobantes en el portal no es la regla que condiciona el envío de la notificación.

## P-006 (propuesta) ✔✘ — Importación de Carta Marina con mapeo simple de columnas
- C-014: **mismo** · difiere: propuesta: importación masiva de nodos, rutas y recorridos; reunión: solo mapeo simple de columnas y persistencia de la Carta Marina, con limpieza y transformación a cargo de LogiCorp fuera del sistema · Es la misma importación masiva del maestro de nodos, con un alcance reducido.
- C-032: **distinto** · Solo comparten el mecanismo genérico de importar; el requisito no pide reglas de validación, sino un mapeo simple.

## P-017 (propuesta) ✔✘ — Campos obligatorios de números de contrato en el alta de elección
- C-266: **mismo** · difiere: propuesta: configurar una nueva elección; reunión: el alta de elección suma tres campos obligatorios de números de contrato (Notificaciones, Distribución de Urnas, Material Electoral) · Es el mismo alta o configuración de una nueva elección en Multielección, con campos adicionales.
- C-267: **distinto** · Es un compromiso genérico de configuración por elección; los campos de contrato corresponden al alta de la elección (C-266).

## P-020 (propuesta) ✔✔✔✔ — Exclusión del MVP: plantillas de impresión, impresión centralizada y generación física de notificaciones
- C-089: **mismo** · difiere: propuesta: soporte a impresión en origen, nodo, sucursal u organismo; reunión: la impresión centralizada y la generación física quedan fuera del MVP · La exclusión recae sobre esta misma funcionalidad de impresión de la Notificación DMS.
- C-091: **mismo** · difiere: propuesta: modelo de nota personalizable por elección/cliente; reunión: la edición de plantillas de impresión queda fuera del MVP · La exclusión afecta a la personalización de las notas de notificación del mismo módulo.
- C-092: **mismo** · difiere: propuesta: plantilla con variables y branding básico; reunión: la edición de plantillas de impresión queda fuera del MVP · La exclusión recae sobre la configuración de plantillas de la Notificación DMS.
- C-295: **mismo** · Ambos dejan la impresión física fuera del sistema; son consistentes.

## P-026 (propuesta) ✔✘✘ — Notificación de pago por correo a autoridades con enlace al portal
- C-110: **mismo** · difiere: propuesta: notificar pago rechazado o confirmado; reunión: correo con enlace al portal de autogestión para ver y descargar el comprobante · Es la misma notificación de pago a la autoridad, con el detalle del enlace al portal.
- C-101: **distinto** · El compromiso es la funcionalidad del portal; el requisito es el envío del correo, que solo enlaza al portal.
- C-100: **distinto** · Consultar el estado de pago en el portal es una función distinta del envío de correos de notificación.

## P-051 (propuesta) ✔ — Alta manual de Nodo con título, descripción, dirección y geolocalización
- C-013: **mismo** · difiere: propuesta: crear nodos sin detallar campos; reunión: alta con título, descripción, dirección física y geolocalización manual · Es el mismo alta de nodos del maestro de nodos.

## P-068 (propuesta) ✔ — Alcance MVP limitado a la lógica de Nodos
- C-013: **mismo** · difiere: propuesta: ABM de nodos, rutas y recorridos; reunión: en el MVP solo nodos, con rutas y recorridos pospuestos · Es el mismo compromiso del maestro, con el alcance reducido a nodos.
