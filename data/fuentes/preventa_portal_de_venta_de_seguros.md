---
source_name: Preventa Portal de Venta de Seguros
source_type: preventa
source_date: '2026-10-27'
layout: paginas
fingerprint: fda2433fa86631ec
---
[[página 1]]
Portal de Ventas 
de Seguros 
Marzo - 2026
1

[[página 2]]
Contexto
actual

[[página 3]]
Contexto actual
3
Desarrollar e implementar el Portal Web de Ventas de Seguros de Seguros Supervielle, que 
permita a los asesores comerciales ejecutar el ciclo completo de venta de pólizas, cubriendo los 
siguientes objetivos específico: 
Comercializar seguros de diversos ramos, como Hogar, Vida, Tecno, Celular, Motos y Autos, 
mediante una experiencia digital segura y eficiente. 
La solución utiliza una arquitectura de Backend-for-Frontend (BFF) para integrar múltiples APIs
que permiten identificar clientes por CUIL, precompletar automáticamente sus datos personales y 
ofrecerles productos personalizados según su perfil y tenencia actual. 
El flujo operativo abarca desde la cotización con catálogos especializados como InfoAuto hasta la 
emisión de la póliza y el procesamiento de pagos, garantizando la privacidad mediante una 
política estricta de limpieza de datos al reiniciar cada gestión.

[[página 4]]
Nuestra 
propuesta

[[página 5]]
Objetivo general
Desarrollar e implementar el Portal Web de Ventas de Seguros de Seguros Supervielle, que permita a los asesores comerciales y clientes provenientes de Alianzas 
ejecutar el ciclo completo de venta de pólizas, cubriendo los siguientes objetivos específico: 
• Autenticación segura mediante login con la cuenta Microsoft del tenant de Seguros Supervielle, con redirección a Microsoft para recuperación de contraseña para 
usuarios Asesores comerciales y Administradores. 
• Autenticación para clientes del canal Alianzas mediante validación de un cupón o código de alianza embebido en una URL o QR, sin requerir credenciales 
corporativas. El sistema verifica que la alianza esté activa, que el cupón se encuentre dentro de su período de vigencia y dentro del límite de usos configurado, y 
retorna la configuración visual de la alianza, los productos habilitados y el flag emision_habilitada que determina el comportamiento post-cotización.
• Administración de alianzas mediante un módulo ABMC que permite crear, configurar, activar y desactivar alianzas, definir su identidad visual (logo, colores), los 
productos habilitados, las condiciones del cupón de acceso (vigencia y usos máximos) y el flag emision_habilitada que controla si el flujo post-cotización de cada 
alianza deriva en emisión directa (flag ON) o en captura de solicitud de contacto para gestión manual por el asesor (flag OFF).
• Gestión del cliente a través de la consulta por CUIL, con visualización de tenencia vigente (vía API Tenencias), productos cotizables habilitados para el asesor (vía 
API Oferta), envío de documentación por mail y generación de link de pago para tenencias de aseguradora. 
• Cotización multi-ramo con formulario precargado desde la API Persona (nombre, documento, domicilio), integración con la API de Medios de Pago como campo 
seleccionable, catálogo InfoAuto/Moto para los ramos Motos y Autos, y visualización de coberturas provistas por la API Productos para ramos broker o con contenido 
estático del equipo de Producto para ramos de aseguradora. 
• Emisión de pólizas con datos personales bloqueados, ingreso de datos del bien asegurado (con catálogos según ramo), selección o ingreso manual del medio de 
pago (TC/CBU). El mail de confirmación de emisión es gestionado por los procesos internos del banco en todos los casos; el portal no integra ni dispara 
ninguna API de mail para este fin.
• Gestión de solicitudes de contacto (leads) para el canal Alianzas con flag OFF, donde el cliente completa un formulario de contacto post-cotización que queda 
registrado en la base de datos. El asesor comercial visualiza y gestiona el estado de las solicitudes directamente desde el portal, con la posibilidad de iniciar el circuito 
de emisión directamente desde una solicitud de contacto.
• Backend propio como capa de seguridad que centralice todas las llamadas a APIs externas (Persona, Tenencias, Oferta, Productos, Medios de Pago, catálogos e 
InfoAuto/Moto) para no exponer API Keys en el frontend. 
• Integridad del flujo: conservar todos los datos del cliente durante la experiencia de cotización/emisión y eliminarlos completamente al regresar al Main, garantizando 
que cada nueva sesión parta desde cero. 
5

[[página 6]]
FEATURE
- Login
- Resetear 
contraseña
Autenticación 
y Acceso
Portal de Ventas de Seguros 
Arquitectura e integraciones
Actor 2 Asesor comercial
FEATURE
- Consulta de tenencias y 
oferta por cliente
- Mostrar tenencia
- Enviar documentación 
de pólizas
- Envío de cupón de 
pago
- Mostrar productos 
cotizables
- Visualizar productos para 
No clientes por botón “No 
soy cliente”
Portal Principal y 
Gestión del Cliente
FEATURE
- Generación de cotización 
de producto
- Precarga de datos 
para clientes 
existentes en 
formulario
- Carga de datos para 
NO clientes
- Visualizar cotización y 
documentos de póliza
Circuito de Cotización 
FEATURE
- Generar emisión de póliza 
(incluye Aliazas solo flag
ON)
- Seleccionar medio de 
pago
- Visualizar datos de 
póliza si la emisión fue 
exitosa
- Visualizar errores si la 
emisión fue fallida
- Volver a enviar a 
recotizar
Circuito de Emisión 
FEATURE
Stack Tecnológico
- Descripción
FEATURE
Infraestructura
- Descripción
Procesos automáticos
- Limpieza estricta de datos al reiniciar flujo
- Carga de documentación de productos 
para pólizas 
- Carga de los parámetros de Look & Feel
(Alianzas y Brokers)
Migración de datos
- No Incluido
Pilares del negocio
La plataforma centraliza la venta de seguros multi-ramo (Hogar, Vida, Tecno, Celular, Motos y Autos), permitiendo la identificación de clientes para la cotización y 
emisión de pólizas mediante integraciones de backend para no exponer las API Keys.
6
Integraciones
- Autenticación: Login Microsoft 
- API Persona, Tenencias y Ofertas
- API Productos
- API COELSA
- API Catálogos Externos 
(InfoAuto/InfoMoto)
- API Medios de Pago
- API Botón de pago
- API Descarga de póliza
- API Envío de mails (envío de 
documentación de póliza)
Administración
FEATURE
- ABMC de Usuarios
- ABMC de Roles
- ABMC de Alianzas
Administrador Cliente Alianzas
FEATURE
- Acceso por QR 
o URL con 
cupón de 
referido
FEATURE
- Visualizar productos 
cotizables habilitados para 
la alianza activa
FEATURE
- Completar formulario de 
contacto post-cotización
(solo flag OFF)
- Visualizar resumen 
de cobertura 
seleccionada (solo 
lectura)
- Generar solicitud 
de contacto
Gestión de solicitud 
de contacto
FEATURE
- Visualizar solicitudes de 
contacto (flag OFF)
- Cambiar estado de 
solicitudes de 
contacto

[[página 7]]
Funcionalidades & Procesos
Web - Autenticación y Acceso – Asesor comercial
7
Objetivo del Servicio
Implementar el acceso al portal mediante autenticación API REST con la cuenta 
Microsoft del tenant de Seguros Supervielle.
Alcance y Actividades Esperadas
• Login: el usuario ingresa usuario y contraseña de Microsoft. Solo usuarios dados de 
alta en el tenant de Seguros Supervielle pueden acceder.
• "Olvidé mi contraseña": redirige al reset password de Microsoft. No requiere 
tratamiento dentro del portal.
• El servicio de autenticación es una API REST
Requerimientos Funcionales
• Autenticar asesores contra el servicio Microsoft del tenant de Seguros Banco vía API 
REST.
• Redirigir "Olvidé mi contraseña" al portal de Microsoft.
• Una vez autenticado, resolver el broker/canal del asesor para determinar look & feel y 
productos habilitados.
Requerimientos Técnicos del Servicio
• Integración con servicio de autenticación Microsoft vía API REST

[[página 8]]
Funcionalidades & Procesos
Web - Autenticación y Acceso – Cliente Alianzas
8
Objetivo del Servicio
Implementar el acceso al portal para clientes finales mediante la validación de 
un cupón o código de alianza embebido en una URL o QR. No se requieren 
credenciales corporativas. El sistema identifica la alianza activa, verifica su 
vigencia y habilita el flujo de cotización personalizado para esa alianza. El portal 
adopta la identidad visual de la institución aliada y le presenta los productos 
disponibles para esa alianza.
Alcance y Actividades Esperadas
• Acceso por QR o URL: el cliente escanea un QR o ingresa a una URL que 
contiene el código de alianza y/o cupón de referido como parámetro.
• El BFF valida el código recibido: verifica que la alianza existe, está activa, y 
que el cupón se encuentra dentro de su período de vigencia y límite de usos 
configurado.
• En caso de código inválido, vencido o con usos agotados: se muestra un 
mensaje de error claro. No se permite el acceso al flujo de cotización.
• No existe pantalla de login con usuario y contraseña. El acceso es directo 
desde el QR/URL.
• No existe opción de "Olvidé mi contraseña" ni ningún mecanismo de 
recuperación de credenciales.
• Una vez validado el cupón, el sistema inicia una sesión de tipo alianza: carga 
la configuración visual de la alianza (look & feel), los productos habilitados y 
el flag emision_habilitada.
Requerimientos Funcionales
• Validar el código de alianza/cupón recibido por parámetro en la URL contra la 
tabla alianzas de la base de datos.
• Verificar estado activo de la alianza, vigencia temporal del cupón y cantidad 
de usos disponibles.
• Mostrar mensaje de error descriptivo si el acceso no es válido (alianza 
inactiva, cupón vencido, usos agotados).
• Iniciar sesión de tipo alianza con configuración visual, productos habilitados y 
flag de emisión resueltos desde la base de datos.
• No requerir ningún tipo de credencial por parte del cliente final.
Requerimientos Técnicos del Servicio
• La respuesta del endpoint incluye toda la configuración de sesión necesaria 
para iniciar el flujo sin consultas adicionales

[[página 9]]
Funcionalidades & Procesos
Web - Portal Principal y Gestión del Cliente –
Asesor comercial
9

[[página 10]]
Funcionalidades & Procesos
Web - Portal Principal y Gestión del Cliente –
Asesor comercial
10
Objetivo del Servicio
Pantalla principal del portal donde el asesor consulta al cliente por CUIL, 
visualiza su tenencia, accede a los productos cotizables habilitados y ejecuta 
acciones complementarias (envío de documentación, generación de link de 
pago).
Alcance y Actividades Esperadas
• Formulario con campo CUIL. Consulta a API Tenencias y API Oferta (por 
cliente + canal/broker del asesor).
• Botón "No soy cliente": saltea validación de CUIL y habilita todos los 
productos del asesor.
• Si se encuentra el cliente: mostrar tenencia vigente, permitir enviar 
documentación al mail del cliente (el registrado o el que declare), y generar 
link de pago vía API Botón de Pago para tenencias de aseguradora.
• Mostrar cards de productos cotizables habilitados según API Oferta. Ramos 
Tecno y Celular muestran cards separadas. El backend detecta el código de 
producto correcto por ramo.
• Regreso al Main desde cualquier punto: eliminar todos los datos del cliente y 
restablecer el flujo.
Requerimientos Funcionales
• Consultar tenencia del cliente via API Tenencias usando el CUIL ingresado.
• Consultar productos cotizables via API Oferta para el cliente y el asesor.
• Mostrar tenencia del cliente con opción de envío de documentación al mail
por API de envio de mails
• Generar link de pago cuando el cliente posee tenencias de aseguradora.
• Mostrar cards de productos cotizables habilitados para el asesor.
• Cards diferenciadas por ramo: Tecno y Celular como cards separadas.
• Botón "No soy cliente" para operar sin validación de CUIL.
• Limpieza total del estado al regresar al Main en cualquier momento.
Requerimientos Técnicos del Servicio
• Integración con API Tenencias.
• Integración con API Oferta.
• Integración con API Botón de Pago
• Integración con API Envio de mails
• Integración con API Persona para autocompletar datos del cliente 
• El backend debe detectar el código de producto correcto por ramo.
• El canal/broker se resuelve desde el usuario autenticado

[[página 11]]
Funcionalidades & Procesos
Web - Portal Principal y Gestión del Cliente –
Cliente Alianzas
11

[[página 12]]
Funcionalidades & Procesos
Web - Portal Principal y Gestión del Cliente –
Cliente Alianzas
12
Objetivo del Servicio
La pantalla principal del canal Alianzas donde el cliente final, una vez validado 
su cupón, puede opcionalmente ingresar su CUIL para precargar datos, 
visualiza los productos cotizables habilitados para su alianza y accede al 
circuito de cotización. No existen acciones de tenencia ni generación de link de 
pago en este canal.
Alcance y Actividades Esperadas
• Campo CUIL opcional. Si el cliente lo ingresa: consulta a API Persona para 
precargar datos en el formulario de cotización. Si no lo ingresa: avanza con 
formulario vacío.
• Mostrar cards de productos cotizables habilitados para la alianza activa. Los 
productos disponibles están configurados en la tabla alianzas (y/o parámetro 
en API Oferta — a confirmar en Fase de Inception). Ramos Tecno y Celular 
muestran cards separadas.
• Iniciar el circuito de cotización de los productos cotizables.
• Regreso al inicio desde cualquier punto: eliminar todos los datos del cliente y 
restablecer el flujo de alianza. La sesión de alianza (look & feel y 
configuración) se preserva.
Requerimientos Funcionales
• Si se ingresa CUIL, consultar datos del cliente vía API Persona y 
precargarlos en el formulario de cotización.
• Si no se ingresa CUIL, habilitar el flujo de cotización con formulario vacío sin 
validación adicional.
• Mostrar cards de productos cotizables habilitados para la alianza activa.
• Cards diferenciadas por ramo: Tecno y Celular como cards separadas. El 
backend detecta el código de producto correcto por ramo.
Requerimientos Técnicos del Servicio
• Integración con API Persona para autocompletar datos del cliente 
(condicional: solo si se ingresa CUIL).
• Los productos habilitados por alianza se resuelven desde tabla alianzas en 
base de datos y/o parámetro en API Oferta (a definir en Fase de Inception)
• El backend detecta el código de producto correcto por ramo.
• La alianza activa se resuelve desde el contexto de sesión establecido en la 
validación del cupón

[[página 13]]
Funcionalidades & Procesos
13
Web - Circuito de Cotización – Asesor Comercial 
/Cliente Alianzas

[[página 14]]
Funcionalidades & Procesos
Web - Circuito de Cotización – Asesor Comercial 
/Cliente Alianzas
14
Objetivo del Servicio
Implementar el formulario de cotización con datos precargados desde las APIs del 
banco (API Persona, API Productos), integración con catálogos externos, 
visualización de coberturas disponibles y selección de la cobertura a emitir. El 
circuito opera en dos canales diferenciados: el canal del Asesor comercial, donde 
el asesor comercial gestiona la cotización en nombre del cliente, y el canal 
Clientes de Alianzas, donde el cliente final completa o confirma sus propios datos 
y avanza al flujo post-cotización determinado por el flag emision_habilitada de la 
alianza: 
• Emisión directa de la poliza (flag ON) 
• Generación de solicitud de contacto para gestión manual (flag OFF)
Alcance y Actividades Esperadas
• Formulario precargado con datos de API Persona: nombre, documento, 
domicilio, etc. Pueden venir campos nulos; el formulario deberá manejarlos 
como campos editables vacíos.
• Cliente nuevo: formulario completo cargado por el Asesor Comercial o Cliente 
Alianzas. 
• Cliente existente: datos personales precargados y editables antes de cotizar.
• Información adicional requerida se obtiene desde el catálogo de InfoAuto/Moto 
via API REST
• Integración con API de medios de pago como campo seleccionable. En caso de 
que la API no retorne opciones (cliente no bancario), se habilita el ingreso 
manual de TC o CBU directamente.
• Coberturas broker: logos, compañías, detalles y condiciones provistos por la 
respuesta de API Productos.
• Coberturas aseguradoras: logo de la alianza activa (vía Marca Blanca) + 
términos y condiciones cargados desde tabla de base de datos vía script 
provisto por el área de Producto.
• Posibilidad de recotizar: el cliente puede volver al formulario sin perder la 
información almacenada.
• (Solo en el canal de Clientes Alianzas) Al seleccionar cobertura, el sistema 
evalúa automáticamente el flag emision_habilitada: si está ON avanza al 
circuito de emisión; si está OFF avanza al formulario de solicitud de contacto 
(sin intervención del usuario) con mensaje de respuesta al Cliente donde se 
informa que será contactado por un Asesor.
• Regreso al Main: EN TODOS LOS CASOS elimina la información del cliente y 
reinicia el flujo.

[[página 15]]
Funcionalidades & Procesos
15
Requerimientos Funcionales
• Precargar formulario con datos de API Persona si se ingresó CUIL; todos los 
campos nulos o ausentes se muestran como vacíos editables.
• Integrar catálogos: InfoAuto/Moto para ramos Motos y Autos.
• Integrar API de medios de pago como campo seleccionable. Si retorna vacío, 
habilitar ingreso manual de TC o CBU sin bloquear el flujo.
• Mostrar coberturas con datos de coberturas definidas por Broker o desde tabla 
de base de datos (aseguradora).
• Permitir recotizar volviendo al formulario sin perder información.
• (Solo en el canal de Clientes Alianzas) Al finalizar la selección de cobertura, 
el sistema evalúa el flag emision_habilitada de la alianza activa y enruta 
automáticamente: flag ON → circuito de emisión; flag OFF → formulario de 
solicitiud de contacto.
Requerimientos Técnicos del Servicio
• Integración con API Persona (condicional: solo si el cliente ingresó CUIL)
• Integración con catálogo InfoAuto/Moto para Motos y Autos
• Integración con API de medios de pago 
• Integración con API Productos para cotización multi-ramo
• Backend debe detectar y usar el código de producto correcto 
(broker/aseguradora).
• Términos y condiciones de aseguradora: tabla de base de datos, carga vía 
script.
• El BFF incluye el flag emision_habilitada en el contexto de sesión de alianza; el 
frontend lo consume para enrutar post-cotización sin consulta adicional al 
backend.
• El logo aplicado en coberturas aseguradoras corresponde a la alianza activa, no 
al bróker
NOTA: La posibilidad de que el cupón de acceso de la alianza lleve asociado un 
beneficio comercial aplicable durante la cotización (por ejemplo, un descuento 
sobre el valor de la prima, una cobertura adicional sin costo u otro beneficio 
promocional) queda pendiente de definición durante la etapa de Inception. 
Web - Circuito de Cotización – Asesor Comercial 
/Cliente Alianzas

[[página 16]]
Funcionalidades & Procesos
Web – Gestión de solicitud de contacto – Cliente Alianzas
16
Objetivo del Servicio
Pantalla de cierre del flujo de cotización para clientes de alianzas cuya alianza 
tiene el flag emision_habilitada en OFF. Una vez seleccionada la cobertura, el 
cliente completa un formulario de contacto que queda registrado en la base de 
datos como solicitud para su posterior gestión manual por parte del banco. No se 
realiza ninguna emisión ni se integra ninguna API externa nueva en este circuito.
Alcance y Actividades Esperadas
• Al finalizar la selección de cobertura, el sistema detecta automáticamente que el 
flag emision_habilitada de la alianza está en OFF y redirige al formulario de 
solicitiud de contacto sin intervención del cliente.
• El formulario solicita los datos de contacto del cliente: nombre, apellido, email y 
teléfono. Todos los campos son obligatorios.
• Ramo, cobertura elegida y suma asegurada se muestran como datos de 
resumen no editables, tomados directamente de la cotización realizada.
• El botón de acción se presenta como "Solicitar contacto", dejando en claro que 
no se está emitiendo en el momento.
• Al confirmar, el BFF graba el contacto en una tabla de Base de datos con todos 
los datos del cliente, la cobertura seleccionada, la alianza de origen, la fecha y 
el estado inicial PENDIENTE.
• Pantalla de confirmación: mensaje "Nos comunicaremos a la brevedad" con los 
datos de contacto ingresados por el cliente. Botón Finalizar que limpia todo el 
flujo.
• No se dispara ninguna llamada a API externa: ni emisión, ni mail, ni notificación. 
El seguimiento del contacto es responsabilidad de los procesos internos del 
banco.
Requerimientos Funcionales
• Detectar automáticamente el flag emision_habilitada = false al finalizar la 
cotización y enrutar al formulario de captura de contacto.
• Validar que todos los campos de contacto estén completos antes de permitir el 
envío (nombre, apellido, email, teléfono).
• Mostrar resumen de cotización (ramo, cobertura, suma asegurada) como 
campos de solo lectura, no editables por el cliente.
• Al confirmar, grabar la solicitud de contacto en la tabla de base de datos con 
estado inicial PENDIENTE.
• Mostrar pantalla de confirmación con datos de contacto ingresados y mensaje 
de contacto próximo.
• Limpieza total del estado del cliente al presionar Finalizar. La sesión de alianza 
(look & feel y configuración) se preserva.
Requerimientos Técnicos del Servicio
• El estado inicial de la solicitud se graba como PENDIENTE
• No integrar ninguna API externa en este circuito. La solicitud de contacto queda 
exclusivamente en una tabla de base de datos

[[página 17]]
Funcionalidades & Procesos
Web – Gestión de solicitud de contacto – Asesor comercial
17
Objetivo del Servicio
Permitir al asesor comercial visualizar y gestionar el estado de las solicitudes de contacto 
generados por el canal de Alianzas directamente desde el portal, cambiando su ciclo de vida de 
PENDIENTE a EN GESTION y finalmente a CERRADO. Si el cliente manifiesta su interés durante 
la gestión, el asesor puede iniciar el circuito de emisión directamente desde esta sección; al 
completarse exitosamente, la solicitud pasa de forma automática a estado CERRADO. Las 
gestiones de contacto con el cliente y seguimiento se realizan por fuera del portal en un sistema o 
circuito a confirmar durante la etapa de Inception.
Alcance y Actividades Esperadas
• El asesor accede a una sección de gestión de solicitudes de contacto dentro del portal donde 
visualiza el listado de solicitudes de contacto generados por el canal de Alianzas, filtrable por 
estado, alianza de origen, ramo y fecha de generación.
• El asesor selecciona una solicitud de contacto con estado PENDIENTE y lo toma para gestión, 
cambiando su estado a EN GESTION. Este cambio queda registrado con fecha, hora y el 
usuario que lo realizó.
• Si durante la gestión externa el cliente confirma su interés, el asesor puede iniciar el circuito de 
emisión directamente desde la solicitud de contacto en estado EN GESTION, sin necesidad de 
volver al Portal Principal. Los datos de la cotización (ramo, cobertura, suma asegurada) se 
precargan automáticamente en el formulario de emisión.
• Si la emisión es exitosa, la solicitud de contacto pasa automáticamente a estado CERRADO con 
motivo CON CONVERSION y se registra el número de póliza. El asesor no necesita cerrar 
manualmente la solicitud en este caso.
• Si la emisión falla, la solicitud de contacto permanece en estado EN GESTION. El asesor puede 
corregir los datos y reintentar, o cerrar manualmente la solicitud con el motivo correspondiente.
• Una vez finalizada la gestión externa SIN emisión desde el portal, el asesor regresa y cierra 
manualmente la solicitud seleccionando el motivo correspondiente. El estado pasa a 
CERRADO.
• Una solicitud de contacto cerrada no puede volver a un estado anterior.
Requerimientos Funcionales
• Mostrar listado de solicitud de contacto con todos los campos disponibles: nombre, apellido, 
email, teléfono, CUIL (si fue ingresado), ramo, cobertura, suma asegurada, alianza de origen, 
fecha de generación y estado actual.
• Permitir al asesor cambiar el estado de una solicitud de contacto de PENDIENTE a EN 
GESTION con un único botón de acción. Registrar fecha, hora y usuario del cambio.
• Permitir filtrar solicitudes de contacto por estado, alianza de origen, ramo, fecha de generación y 
cualquier combinación de estos campos.
• Habilitar el botón "Iniciar emisión" únicamente sobre solicitudes de contacto en estado EN 
GESTION. No debe estar disponible en estado PENDIENTE ni CERRADO.
• Al completarse una emisión exitosa iniciada desde una solicitud de contacto, cerrar 
automáticamente la solicitud con estado CERRADO, motivo CON CONVERSION y número de 
póliza registrado. Sin intervención adicional del asesor.
• Si la emisión falla, mantener la solicitud en estado EN GESTION. Permitir al asesor corregir y 
reintentar, o cerrar manualmente con motivo de cierre.
• Una solicitud de contacto en estado CERRADO no puede modificarse ni reabrir. El cambio de 
estado es irreversible desde el portal.
Requerimientos Técnicos del Servicio
• Registrar todos los cambios de estado en la tabla de solicitudes de contacto de la base de datos
• No se integra ningún sistema externo de gestión de contacto, CRM ni canal de emisión externo. 
El portal únicamente gestiona el estado de la solicitud de contacto e inicia el circuito de emisión 
interno.

[[página 18]]
Funcionalidades & Procesos
Web - Circuito de Emisión – Asesor comercial / 
Cliente Alianzas
18
A continuación, describimos a 
alto nivel los posibles estados
que irán tomando las pólizas 
emitidas.
Emitida: Indica el momento en 
que una póliza fue emitida, 
Con errores: Indica el momento 
en que se recibieron errores 
durante la generación de la 
póliza

[[página 19]]
Funcionalidades & Procesos
19
Objetivo del Servicio
Flujo completo de emisión de pólizas cubriendo dos perfiles de usuario sobre 
la misma plataforma: el asesor comercial, que opera en nombre de un cliente 
final con datos bloqueados desde la cotización; y el cliente final del canal 
Alianzas, que confirma sus propios datos y avanza a la emisión cuando el flag
emision_habilitada de la alianza está en ON. 
En ambos casos el flujo cubre el ingreso y validación del medio de pago, los 
datos del bien asegurado, la emisión vía API Productos, la descarga de póliza y 
el manejo de resultado exitoso y error. El mail de confirmación de emisión es 
gestionado por los procesos internos del banco en todos los casos; el portal no 
integra ni dispara ninguna API de mail en ningún perfil ni circuito.
Alcance y Actividades Esperadas
• El usuario no puede modificar datos personales de cotización sin recotizar.
• Medio de pago — cliente existente: precargar máximo 2 opciones bancarias 
(sin paginación); permitir agregar TC o CBU como alternativa.
• Medio de pago — cliente nuevo: ingresar TC o CBU. El CBU se valida en 
tiempo real mediante API Coelsa.
• Datos del bien asegurado: ingreso de datos según ramo, con posible 
integración de catálogos adicionales en emisión.
• Emisión vía API Productos: el backend determina el endpoint correcto 
(broker/aseguradora).
• Descarga de póliza: integración con API de descarga — endpoint de broker o 
aseguradora según tipo de póliza emitida (en alcance de esta versión por 
requerimiento de Marca Blanca).
• Mail de confirmación: gestionado por los procesos internos del banco al 
emitirse la póliza. El portal NO integra ni dispara API de mail en este circuito.
• (Para Asesores comerciales) Pantalla de éxito: número de póliza + botón 
de retorno al Main (limpia todo el flujo).
• (Para Clientes de Alianzas) Pantalla de éxito : número de póliza + botón 
Finalizar (limpia todo el flujo de alianza).
• Pantalla de error: mensaje de la API + posibilidad de corregir bien asegurado 
y/o medio de pago. Datos personales NO modificables sin recotizar.
Web - Circuito de Emisión – Asesor Comercial 
/Cliente Alianzas

[[página 20]]
Funcionalidades & Procesos
20
Requerimientos Funcionales
• Bloquear modificación de datos personales en pantalla de emisión.
• Precargar hasta 2 medios de pago bancarios del cliente (sin paginación).
• Validar CBU nuevo ingresado mediante API Coelsa
• Emitir póliza vía API Productos (endpoint broker o aseguradora según tipo).
• Descargar póliza emitida vía API de descarga (endpoint broker o aseguradora).
• Mostrar número de póliza en pantalla de éxito.
• En error: mostrar respuesta de la API y permitir corrección de bien/medio de 
pago.
Requerimientos Técnicos del Servicio
• Integración con API Productos para emisión 
• Integración con API Coelsa para validación de CBU 
• Integración con API de Descarga de póliza.
• Integración con API de Medios de Pago.
• El BFF identifica el tipo de sesión activa (Asesor comercial o Cliente de alianza) 
y aplica la lógica diferenciada correspondiente en cada endpoint
• NO se integra API de envío de mail en ningún perfil ni circuito. El mail de 
confirmación es responsabilidad exclusiva de los procesos internos del banco
Web - Circuito de Emisión – Asesor Comercial 
/Cliente Alianzas

[[página 21]]
Funcionalidades & Procesos
Web - Administración – Administrador
21
ABMC de Usuarios
Objetivo del Servicio
Proveer un módulo de gestión completa de usuarios asesores, incluyendo la 
asignación del broker al que pertenece cada usuario, lo cual determina su 
canal, look & feel y funcionalidades habilitadas.
Alcance y Actividades Esperadas
• Alta, Baja, Modificación y Consulta (ABMC) de usuarios asesores.
• Cada usuario debe tener asignado el broker al que pertenece. Este dato es 
utilizado como parámetro de canal en la API Oferta y determina el look & 
feel del portal.
• Asignación de rol a cada usuario (vinculado con el módulo de Roles y 
Permisos).
• Requerimientos Funcionales
• CRUD completo de usuarios con campos: nombre, usuario, email, broker
asignado, rol, estado (activo/inactivo).
• Validación de unicidad de usuario.
• Filtro y búsqueda de usuarios por nombre, broker y estado.
• Un usuario sin broker asignado no puede operar el portal de ventas.
• Requerimientos Técnicos del Servicio
• Tabla de usuarios en base de datos
ABMC de Roles
Objetivo del Servicio
Proveer un módulo para definir roles con permisos granulares sobre las 
funcionalidades del portal, permitiendo controlar el acceso de cada asesor 
según su perfil.
Alcance y Actividades Esperadas
• Alta, Baja, Modificación y Consulta (ABMC) de roles.
• Asignación de permisos a cada rol sobre las funcionalidades del portal 
(cotización, emisión, administración de usuarios, etc.).
• Asignación de rol a usuarios desde el módulo de Administración de 
Usuarios.
Requerimientos Funcionales
• CRUD completo de roles con nombre y descripción.
• Asignación/revocación de permisos por funcionalidad a cada rol.
• El perfil del asesor autenticado determina qué secciones del portal puede 
ver y operar.
Requerimientos Técnicos del Servicio
• Tablas de roles y permisos en base de datos

[[página 22]]
Funcionalidades & Procesos
Web - Administración – Administrador
22
ABMC de Alianzas
Objetivo del Servicio
Módulo de administración que permite crear, configurar, activar y desactivar alianzas desde el 
portal. Centraliza la gestión de la identidad visual de cada alianza, los productos habilitados, las 
condiciones del cupón de acceso y el flag emisión_habilitada que determina el comportamiento 
post-cotización del canal Alianzas. 
Alcance y Actividades Esperadas
• Alta de alianza: creación de una nueva alianza con todos sus campos de configuración: 
nombre, institución aliada, logo, colores, vigencia del cupón, usos máximos, estado inicial, 
productos habilitados y flag de emisión_habilitada
• Modificación de alianza: edición de cualquier campo de configuración de una alianza 
existente, incluyendo el flag emisión_habilitada. El cambio tiene efecto inmediato sobre 
nuevos accesos.
• Baja / desactivación de alianza: cambio de estado a inactivo. Una alianza inactiva rechaza 
inmediatamente cualquier acceso, aunque el cupón sea técnicamente válido. No se elimina el 
registro de la base de datos.
• Consulta y listado: visualización de todas las alianzas con filtros por nombre, estado y 
vigencia. Permite identificar alianzas activas, vencidas o próximas a vencer.
• Generación del QR y/o URL de acceso por alianza: el sistema genera el enlace de acceso 
parametrizado con el código de la alianza, listo para ser embebido en un QR o distribuido 
digitalmente.
• La carga inicial de alianzas y su configuración visual se realiza vía script SQL. El módulo 
permite la gestión posterior en el tiempo sin necesidad de intervención técnica.
Requerimientos Funcionales
• Permitir la edición completa de todos los campos de una alianza existente.
• El flag emisión_habilitada debe ser claramente distinguible en el formulario: ON = cotización + 
emisión directa / OFF = cotización + generación de solicitud de contacto.
• Cambio de estado activo/inactivo con efecto inmediato. Una alianza inactiva bloquea el acceso 
aunque el cupón sea técnicamente válido.
• Listar alianzas con filtros por nombre, estado y vigencia. Indicar visualmente alianzas próximas 
a vencer.
• Generar y mostrar la URL de acceso parametrizada por alianza. Permitir copiarla o descargar el 
QR correspondiente.
• Cancelar solicitudes de contacto con estado PENDIENTE cuando se desactiva una alianza.
• Requerimientos Técnicos del Servicio
• Endpoint BFF para generación de URL parametrizada y QR por alianza
• Tabla en la base de datos para entidad de Alianzas
• La configuración visual (logo, colores) de la alianza debe quedar disponible en la respuesta de 
validación de cupón para ser aplicada inmediatamente por el frontend
• Script de carga inicial de alianzas 
NOTA  
• Se asume que el cupón de acceso tiene fecha de vencimiento y cantidad máxima de usos configurables de 
forma independiente por alianza. Ambos parámetros son obligatorios al dar de alta una alianza.
• Se asume que el cupón de cada alianza puede ser utilizado por distintos clientes (no es de uso único por 
persona). Si el cupón está vencido o con usos agotados, se muestra un mensaje de error genérico al 
cliente final. No se contempla personalización en el contenido del mensaje de error por alianza.

[[página 23]]
Funcionalidades & Procesos
Carga de los parámetros de Look & Feel
Procesos automáticos
23
Objetivo del Servicio
El portal debe personalizar su apariencia visual según el canal activo: en el 
canal de asesores, según el broker del asesor autenticado; en el canal de 
Alianzas, según la alianza validada mediante cupón. En ambos casos la 
configuración se toma desde la base de datos. Esto incluye colores, logo, y 
demás elementos definidos en el manual de marca de cada broker o institución 
aliada.
Alcance y Actividades Esperadas
• Canal Asesor: al autenticarse, el portal resuelve el broker del asesor y carga 
la configuración visual correspondiente (logo, colores, tipografía u otros 
elementos según manual de marca).
• Canal Alianzas: al validar el cupón de referido, el portal resuelve la alianza 
activa y carga su configuración visual (logo de la institución aliada, colores y 
demás elementos de su identidad de marca).
• La configuración de cada broker y de cada alianza se almacena en la base 
de datos (misma lógica de resolución, fuente diferenciada por tipo de sesión).
• La carga inicial de brokers y alianzas con su configuración visual se realiza 
vía script de base de datos (no existe pantalla de administración de look & 
feel en este alcance).
• Requerimientos Funcionales
• Resolución dinámica del look & feel al iniciar sesión (asesor) o al validar el 
cupón (alianzas), según el tipo de sesión activa.
• El frontend aplica los estilos correspondientes al broker o alianza activo sin 
recarga de página.
• Todos los asesores de un mismo broker ven la misma apariencia; todos los 
clientes de una misma alianza ven la apariencia de esa alianza.
• Requerimientos Técnicos del Servicio
• Tabla de configuración visual en base de datos que cubre tanto brokers como 
alianzas
• Script de carga de parámetros de brokers y alianzas 
• El BFF expone la configuración visual al frontend en la respuesta de login
(canal asesor) o en la respuesta de validación de cupón (canal Alianzas).

[[página 24]]
Funcionalidades & Procesos
Carga de documentación de productos para pólizas 
Procesos automáticos
24
Objetivo del Servicio
Administrar el contenido de términos y condiciones de las coberturas de aseguradora, almacenado en tabla de base de datos y 
cargado vía scripts de base de datos a partir de los documentos provistos por el área de Producto.
Alcance y Actividades Esperadas
• Los términos y condiciones de cada cobertura de aseguradora se almacenan en una tabla de base de datos.
• La carga y actualización del contenido se realiza vía scripts SQL ejecutados por el área de Sistemas, a partir de los 
documentos provistos por el área de Producto de Seguros Banco.
• No existe pantalla de administración de contenido de T&C en el alcance de este proyecto.
• Requerimientos Funcionales
• El módulo de cotización debe mostrar los T&C correspondientes a cada cobertura de aseguradora consultando la tabla 
correspondiente de base de datos.
• Los T&C deben diferenciarse por ramo y cobertura.
• Requerimientos Técnicos del Servicio
• Tabla de base de datos de términos y condiciones (ramo, cobertura, contenido).
• Script de cargas de T&C

[[página 25]]
Funcionalidades & Procesos
Limpieza Estricta de Datos al Reiniciar Flujo
Procesos automáticos
25
Objetivo del Servicio
Garantizar que al regresar al Portal Principal (Main) desde cualquier punto del flujo —cotización, emisión o pantalla de resultado—
el estado completo de la sesión del cliente sea eliminado de forma inmediata y total, dejando el portal en condiciones de iniciar 
una nueva cotización desde cero. Este proceso es una regla de negocio crítica que protege la privacidad del cliente anterior y 
evita contaminación de datos entre cotizaciones.
Alcance y Actividades Esperadas
• El proceso se activa ante cualquiera de los siguientes eventos: clic en botón "Regresar al Main", clic en botón "Volver al Main" 
en la pantalla de éxito post-emisión, o navegación directa a la pantalla principal.
• No existe mecanismo de "deshacer" ni recuperación del estado eliminado.
Requerimientos Funcionales
• El botón "Regresar al Main" debe estar visible y accesible en todas las pantallas del flujo: Portal Principal post-consulta, 
formulario de cotización, pantalla de coberturas, pantalla de emisión, pantalla de error y pantalla de éxito.
• La limpieza debe ser total y sin excepciones: ningún dato del cliente anterior debe permanecer visible ni accesible al iniciar una 
nueva operación.
• El flujo "No soy cliente" también activa la misma limpieza al regresar al Main.
• Luego de la limpieza, el portal debe renderizarse exactamente igual al estado inicial de sesión: formulario CUIL vacío y sin 
productos precargados.

[[página 26]]
Integraciones
Autenticación Microsoft 
Objetivo: Autenticar al asesor comercial contra el tenant de 
Microsoft de Seguros Banco. Valida las credenciales y retorna el 
token/sesión que habilita el acceso al portal.
Consideraciones:
• Confirmado por el cliente como API REST 
• "Olvidé mi contraseña" es un redirect externo al portal de 
Microsoft; el portal no interactúa con ninguna API para este caso.
API Persona
Objetivo: Obtener los datos personales del cliente a partir de su 
CUIL para precargar el formulario de cotización
Consideraciones:
• El cliente confirmó que pueden venir campos nulos; el sistema 
debe manejarlos mostrando el campo como vacío y editable, nunca 
como error bloqueante.
API Tenencias
Objetivo: Consultar las pólizas vigentes del cliente identificado por 
CUIL para mostrarlas en el Portal Principal. Permite al asesor 
conocer el estado actual del cliente antes de cotizar.
Consideraciones:
• Se consume en el Portal Principal después de ingresar el CUIL.
API Oferta 
Objetivo: Determinar qué productos de seguro puede adquirir un 
cliente específico, habilitados para el canal/broker del asesor que 
está operando. Su resultado define las cards de productos que se 
muestran en el Portal Principal.
Consideraciones:
• Requiere dos parámetros: CUIL del cliente + canal/broker del 
asesor (confirmado por el cliente: "por cliente + canal").
• El canal/broker se resuelve automáticamente desde el perfil del 
usuario autenticado; el asesor no lo ingresa manualmente.
• En el flujo "No soy cliente", se llama sin CUIL, solo con el 
canal/broker del asesor para mostrar todos sus productos 
habilitados.

[[página 27]]
Integraciones
API Productos — Cotización y Emisión (Broker / Aseguradora)
Objetivo: Ejecutar la cotización y la emisión de pólizas para los seis 
ramos: Hogar, Vida, Tecno, Celular, Motos y Autos. Es la API central 
del negocio.
Consideraciones:
• Tiene dos grupos de endpoints diferenciados: uno para pólizas 
de broker y otro para pólizas de aseguradora. El BFF determina 
cuál usar en base al código de producto obtenido de la API Oferta.
• Se utiliza en dos momentos del flujo: en la cotización (para 
obtener coberturas disponibles con sus precios, logos y 
condiciones) y en la emisión (para confirmar y emitir la póliza).
API Medios de Pago (Banco)
Objetivo: Obtener las opciones de pago bancarias asociadas a un 
cliente para presentarlas como campo seleccionable tanto en la 
cotización como en la pantalla de emisión.
Consideraciones:
• Retorna máximo 2 opciones por cliente (confirmado por el 
cliente); no requiere paginación.
• Se consume en dos momentos: en la cotización (para mostrar 
las opciones disponibles como seleccionable) y en la emisión (para 
precargar los medios de pago del cliente).
API Coelsa — Validación de CBU
Objetivo: Validar en tiempo real que un número de CBU ingresado 
manualmente por el asesor es válido antes de proceder con la 
emisión.
Consideraciones:
• Se invoca únicamente cuando el asesor ingresa o agrega un 
CBU como medio de pago 
• La validación es sincrónica y bloqueante: el flujo no avanza si el 
CBU es inválido; el asesor debe corregirlo.
API Botón de Pago 
Objetivo: Generar un link de pago con tarjeta para clientes que 
tienen tenencias de pólizas de aseguradora vigentes. El link 
generado se envía al mail del cliente.
Consideraciones:
• Se consume exclusivamente desde el Portal Principal, cuando el 
cliente tiene tenencias de aseguradora.
• La API retorna un link (URL) que se envía al cliente por mail; el 
portal no gestiona la pantalla de pago en sí.

[[página 28]]
Integraciones
InfoAuto / InfoMoto (Catálogo de Vehículos)
Objetivo: Proveer los catálogos de marcas, modelos y versiones de 
vehículos para los ramos Motos y Autos, tanto en la pantalla de 
cotización como en la de emisión.
Consideraciones:
• El cliente ya cuenta con la licencia y suscripción a estos 
servicios 
• Se utilizan en dos momentos: cotización (para seleccionar el 
vehículo/moto a cotizar) y emisión (para completar datos del bien 
asegurado, en los casos que lo requieran).
API Descarga de Póliza
Objetivo: Obtener el documento PDF de la póliza recién emitida 
para que el asesor pueda visualizarlo y/o entregarlo al cliente.
Consideraciones:
• Tiene dos endpoints diferenciados: uno para pólizas de broker y 
otro para pólizas de aseguradora. El BFF elige cuál invocar según el 
tipo de póliza emitida.
• Se invoca inmediatamente después de una emisión exitosa, 
antes del envío del mail de confirmación.
API Envio de mails (envio de documentación de póliza)
Objetivo: Permitir al asesor comercial enviar la documentación de 
pólizas vigentes al mail del cliente directamente desde el Portal 
Principal. El BFF actúa como intermediario hacia la API externa de 
envío de mails, sin que el portal gestione ni configure ningún 
servidor de correo propio.
Consideraciones:
• Desde el Portal Principal, al visualizar la tenencia vigente del 
cliente, el asesor dispone de una acción para enviar la 
documentación de la póliza al mail del cliente.
• El mail de destino es el registrado por el cliente en el banco o el 
que el cliente declara en el momento. El asesor puede visualizar el 
mail y confirmarlo antes de enviar.
• El contenido del mail (template, datos que incluye) debe ser 
definido por el cliente. A confirmar en Fase inception.
• La API de mail también puede ser invocada desde el Portal 
Principal para el envío de documentación de pólizas existentes al 
cliente.
• Aplica únicamente en el canal Asesor. El canal Alianzas no 
contempla envío de documentación desde el Portal Principal

[[página 29]]
Infraestructura de Alto Nivel
29

[[página 30]]
Desarrollo - Stack Tecnológico
30
Microsoft Azure es la plataforma en la nube de Microsoft que ofrece una amplia gama de servicios, como computación, almacenamiento,
bases de datos y análisis, para desarrollar, implementar y gestionar aplicaciones. Soporta entornos híbridos y multicloud, facilitando la
integración con sistemas on-premises.. Ofrece escalabilidad flexible, permitiendo ajustar recursos según demanda, y una alta disponibilidad
global gracias a sus múltiples centros de datos. Además, proporciona seguridad avanzada con protección de datos y cumplimiento de
normativas, junto con una amplia gama de servicios para acelerar el desarrollo de soluciones innovadoras.
Azure DevOps es un conjunto de herramientas de desarrollo colaborativas que facilitan la planificación, desarrollo, pruebas y entrega de
aplicaciones. Ofrece beneficios como la integración continua y entrega continua (CI/CD), la gestión de repositorios de código, y la coordinación
de equipos, lo que agiliza los ciclos de desarrollo, mejora la calidad del software y acelera la entrega de productos al mercado.
GitHub es una plataforma de control de versiones basada en Git que permite a los desarrolladores colaborar, gestionar y alojar repositorios de
código de manera eficiente. Ofrece herramientas para revisión de código, integración continua y despliegue, facilitando el desarrollo en equipo
y el manejo de proyectos open source o privados.
Angular se utilizará a pedido del cliente para el desarrollo del frontend, ofreciendo un framework robusto y modular que facilita la creación de
aplicaciones web escalables y de alto rendimiento, con una experiencia de usuario fluida gracias a su arquitectura basada en componentes y
un rico ecosistema de herramientas. Proporciona una estructura robusta para el desarrollo de aplicaciones web escalables y mantenibles, con
un enfoque en la reutilización de componentes

[[página 31]]
Desarrollo - Stack Tecnológico
31
GitHub es una plataforma de control de versiones basada en Git que permite a los desarrolladores colaborar, gestionar y alojar repositorios de
código de manera eficiente. Ofrece herramientas para revisión de código, integración continua y despliegue, facilitando el desarrollo en equipo
y el manejo de proyectos open source o privados.
MySQL DB es una opción popular para quienes buscan una solución de base de datos relacional en la nube con la potencia y flexibilidad , 
una de las bases de datos de código abierto más avanzadas y con una amplia gama de características..
Ofrece una opción poderosa para el almacenamiento y gestión de datos, ofreciendo una combinación de características avanzadas, 
flexibilidad y un modelo de licencia abierto que lo hace adecuado para una amplia variedad de aplicaciones.
Node.js posee una arquitectura no bloqueante basada en eventos, que permite manejar múltiples conexiones simultáneas con alta eficiencia y 
baja latencia, haciéndolo ideal para aplicaciones en tiempo real y sistemas de microservicios.
Ofrece un rendimiento alto y eficiente, una gran flexibilidad y escalabilidad, y un ecosistema rico, todo basado en el popular lenguaje JavaScript. 
Estos beneficios lo convierten en una opción popular para una amplia variedad de aplicaciones y servicios modernos.
Azure Kubernetes Service (AKS) es un servicio gestionado que facilita la implementación, administración y escalado de aplicaciones basadas
en contenedores utilizando Kubernetes. AKS ofrece alta disponibilidad, balanceo de carga automático y recuperación ante fallos, permitiendo a
las empresas concentrarse en el desarrollo y despliegue de aplicaciones sin preocuparse por la infraestructura subyacente.

[[página 32]]
Desarrollo - Stack Tecnológico
32
Azure API Management es un servicio de observabilidad que recopila, analiza y visualiza métricas, logs y trazas de todos tus recursos de
Azure (y externos). Permite detectar problemas, configurar alertas y automatizar respuestas. Se integra con servicios como Application Insights
y Log Analytics para ofrecer monitoreo completo de aplicaciones e infraestructura
Azure Active Directory (Azure AD) es un servicio de gestión de identidades y accesos en la nube que proporciona autenticación segura y
autorización para usuarios y aplicaciones. Ofrece beneficios como la protección de identidades con autenticación multifactor, el acceso
condicional y la gestión unificada de usuarios, lo que facilita el control de acceso seguro a recursos tanto en la nube como on-premises.
Docker se empleará para el despliegue y gestión de contenedores, proporcionando un entorno ligero y portátil que asegura la consistencia en 
el despliegue de aplicaciones, reduciendo problemas de compatibilidad y mejorando la eficiencia de los recursos del sistema. Permite la 
creación, despliegue y ejecución de aplicaciones en contenedores ligeros y portables, mejorando la consistencia del entorno y la eficiencia en 
el uso de recursos.

[[página 33]]
Equipo del 
CLIENTE
Trabajan de manera colaborativa con el resto del equipo. Respetan las buenas prácticas y procesos definidos para el equipo. Aseguran un código limpio
y eficiente basado en las especificaciones del producto. Solucionan problemas, proponen mejoras y son proactivos ante issues de índole técnica. 
Recomiendan y realizas mejoras. Cumplen con la metodología de trabajo y documental definida para la célula de trabajo.
Desarrollador 
Full Stack
CFOTech
Asegurar la calidad del software antes de la implementación en base a casos , condiciones y escenarios de pruebas robustos.QA / QC
CFOTech
Producto Owner: Es el responsable de la administración de los temas que deberán ser llevados a cabo por el servicio de CFOTech. Interpreta los 
objetivos estratégicos y prioridades del negocio, los refleja y prioriza en el backlog de común acuerdo con el Lider de CFOTech. Genera las historias de 
usuario,  genera los test case y los criterios de aceptación de común acuerdo con el Lider de CFOTech.
Lider técnico de integraciones
UX/UI
DevOps
Roles del equipo
33
Diseña y planifica soluciones tecnológicas que resuelvan problemas específicos o que cumplan con objetivos estratégicos de una organización. Trabajar 
con desarrolladores, ingenieros de sistemas, y otros profesionales para garantizar que la solución se implemente correctamente. Coordina con equipos
de proyectos y partes interesadas para asegurar que la solución cumpla con los plazos y presupuestos.
Líder Técnico
CFOTech
NOTA: Se especificaron los perfiles que SUPERVIELLE asignará al proyecto, manteniendo la metodología de trabajo (Inception desk + Agile), donde 
consideramos que los equipos tanto de SUPERVIELLE como CFOTECH participarán en cada etapa dependiendo de la instancia en la que se encuentre el 
proyecto.

[[página 34]]
Entregables
KickOff Inception
Deck (1 semana)
N SPRINT DE DISEÑO – CONSTRUCCION
y PRUEBAS (Integrales)
GESTION  & SEGUIMIENTO
2,5 meses
O
K
U
A
T
• El plan detallado será elaborado de común acuerdo con el Cliente al cumplirse el hito de finalización Inception Deck, en donde se definirá y se priorizará el backlog de trabajo, los test cases y criterios de aceptación a 
partir de los cuales se registrará el cumplimiento de los entregables dentro de los 5 días hábiles posteriores a la entrega y la estrategia de desarrollo e implementación con el cliente.
• La duración de los sprint puede variar entre 2 y 4 semanas según acuerden el PO del cliente y CFOTECH, siendo recomendable ajustar la duración de cada sprint de manera que se asegure la integración de las 
funcionalidades incluidas en cada uno
• El cliente participara de las ceremonias de Refinamiento, Planning, Weekly, Retrospective.
• Cabe aclarar que durante la etapa de Inception Deck, se ajustarán las estimaciones realizadas en función a los cambios de alcance o niveles de complejidad que se detecten al realizar el relevamiento detallado y al 
priorizar las historias de usuario, pudiendo verse impactado el plan de alto nivel presentado. 
• Las etapas con mayor participación por parte de los usuarios son: Inception Deck,( 1 semana) y Pruebas de Usuarios Homologación (UAT acompañamiento de CFOTech durante 1 semana )
Consideraciones sobre la planificación
•Plataforma desarrollada y en funcionamiento en ambiente de UAT
•Código fuente de plataforma implementada.
•Script de base de datos utilizada para la plataforma.
•Documentación técnica.
•Recomendaciones de cara al mantenimiento y soporte de la plataforma.
•Traspaso del conocimiento al equipo de Cliente utilizando la técnica de 
Shadowing en la etapa de UAT
Plan de Trabajo (Alto Nivel)
34

[[página 35]]
Lineamientos Generales
Prioridad Ejemplo Definición Acción a Tomar SLA Análisisy Respuesta
Alta / Crítica
Afecta el uso 
normal del 
sistema
Caída total del sistema o 
proceso de negocio clave. 
Funcionalidad importante 
afectada, sin alternativa
Resolución urgente, 
posible activación de 
Guardia
12 horas hábiles
Media
Impacto 
moderado en
la usabilidad
Funcionalidad degradada, 
alternativa disponible
Programación de 
corrección dentro del día 20 horas hábiles
Baja Impacto menor o sin urgencia Incidencias menores, sin impacto en operación Planificación en backlog para próxima iteración 28 horas hábiles
Tipo de incidencias
Soporte Post Implementación
Nuestra Propuesta
✓ Alcance del Servicio 
Modalidad de Soporte Correctivo será brindado de forma remota
e incluyen el análisis y resolución de incidentes a demanda.
Ventana de Soporte: Días hábiles de 9 a 18
Referentes del Servicio y Puntos de Contacto:
Operación: Responsable Técnico del servicio
Comercial: Gerente Comercial de la cuenta
✓ Paquete mensual de soporte
• 32 HS (del equipo con know how en las tecnologías de la plataforma 
incluida en la propuesta). Horas Incluyen: Análisis de errores en 
ambiente productivo y en caso de aplique, su ponderación de esfuerzo 
y resolución.
• Si el paquete de horas se consume antes de finalizar el mes, 
comercialmente se gestionará las horas que se requieran para 
continuar el soporte.
• El paquete de horas no es acumulable en caso de remanentes.
Se aclara que el SLA se aplica a partir de 
disponer de todos los datos de tickets y solo 
representa el tiempo máximo de análisis del 
error. No aplica a la corrección del mismo.
35

[[página 36]]
Lineamientos Generales
Soporte Post Implementación
Nuestra Propuesta
• Generación de Tickets (Cliente)
Responsable de Evaluación y clasificación (asignar criticidad)
Canal Formal: Las solicitudes deben ser cargadas en el Tablero del Servicio
Canal Alternativo: aviso de temas puntuales vía email al Contacto CFOTECH
Información de incidentes
o Nombre del proceso afectado / Funcionalidad.
o Descripción de la problemática
o Ambiente y versión afectada
o Proceso de Negocio afectado junto con su Impacto en el mismo
o Detalle del Page Flow
o Evidencia (Logs, Print screen, Hora de detección)
• Recepción, Validación, Respuesta y Estimación
El tratamiento será secuencial según fecha de ingreso. En caso de múltiples tickets,
se podrá establecer priorización en conjunto con el cliente.
Se valida la información recibida en el ticket y se intenta reproducir el error.
o Si se reproduce: Se realiza estimación del esfuerzo considerando:
• Análisis funcional y documentación de alto nivel
de la solución
• Horas de desarrollo
• Pruebas
• Soporte a la entrega
Se informa compromiso de entrega
o Si no se reproduce: Se comparten evidencias de no reproducción
Esta Información se detallará en el ticket.
• Desarrollo, Entrega e Integración del Código Fuente
Ambientes de Trabajo y Pasaje a Producción (Se comunica el 
avance al cliente durante todo el proceso):
Desarrollo: implementación y pruebas internas
Etapa Integración: Las correcciones se integran aquí.
Producción: el cliente es responsable del pasaje final
Actualización del ticket notificando la entrega y adjuntando 
evidencias.
Si se requiere asistencia en el pasaje a producción, deberá 
solicitarse previamente y se imputará a las horas técnicas.
• Documentación y Control de Calidad
Cada entrega de solución final se detallará en la herramienta que 
se defina.
Se realizarán controles de calidad internos y se colaborará en 
auditorías del cliente.
• Cierre del Ticket
El cierre se realiza una vez el cliente confirme la validación, por otro 
lado, se documenta causa raíz y actualiza la base de conocimiento 
si corresponde.
Si no hay respuesta en un plazo de 1 semana se considerará 
cerrado automáticamente.
36

[[página 37]]
Cómo
lo haremos

[[página 38]]
Metodología de trabajo
38
1. Misión – ¿Por qué estamos aquí?
Los key Users y el PO comparten la finalidad del proyecto.
2. Objetivos de Negocio – Elevator Pitch
Se detalla de manera resumida el origen de la necesidad indicando
el objetivo del producto o desarrollos y qué equipo, sector o
segmento se benefician con esta oportunidad
3. Objetivos del Producto – Caja del producto
La idea es tener un alto nivel del producto o proceso, que sea lo
suficientemente capaz de mostrar las características específicas del
proyecto, indicando además sus beneficios
4. Alcance – Lista de lo que NO es
Identificamos tres secciones que indiquen, Dentro del alcance,
Fuera del alcance y Sin Decidir. Se enumeran todos los artículos
importantes del proyecto y se agrupan (Product Backlog)
5. Equipo – Comunidad del Proyecto
Identificamos a todas las personas con las que se tendrá que
interactuar en el transcurso del proyecto y así comenzar a
establecer responsabilidades y relacionamiento
6. Necesidades – Funcional/Técnica/UX-UI
Identificamos las necesidades funcionales, técnicas y de diseño del proyecto
junto a features de la arquitectura, ambientes y aplicativos satélites.
7. Riesgos – ¿Qué nos impide dormir?
Identificamos los riesgos indicando el impacto que tendría en caso de
materializarse y la probabilidad de que ocurra.
8. Dimensionamiento – Tamaño del proyecto
En esta dinámica se revisa el número de personas involucradas y los tiempos
que se manejan para cumplir con las necesidades de negocio.
9. Factores Claves – Tiempo/Alcance/Dinero
En todo desarrollo de producto debemos ser flexibles en algunos aspectos, pero
en otros no, establezcamos donde podemos ceder cuando se presente alguna
situación y cuando no. ¿Es calidad, dinero, flexibilidad, simplicidad?
10. Fechas – Camino del Proyecto
Revisamos el macro-plan que se tiene para construir. Dimensionamos el
producto o MVP, priorizamos las Épicas, User Stories dentro del Product Backlog
y revisamos los costos asociados.
Estrategia de Inception ( primera etapa a partir de la propuesta técnica)

[[página 39]]
Nuestra propuesta se basa en brindar
un Squad de Desarrollo integrado por expertos en el 
desarrollo de software,
que trabajarán de cerca con el equipo
de Cliente en el entendimiento del negocio, análisis y  
diseño detallado, desarrollo, calidad y estabilización de 
las iniciativas y requerimientos, en ciclos de desarrollo e 
implementación de evolución continua.
Nuestros esfuerzos estarán enfocados en integrarnos 
completamente con el equipo de Cliente, trabajando 
bajo metodología SCRUM guiada por el backlog de 
historias de usuario con la debida priorización.
Metodología de trabajo
39
Scrum - Agile

[[página 40]]
Cliente
Responsable
del Proyecto
Product Owner
Equipo
del Cliente
Service Manager
Líder del Equipo
Equipo
de CFOTech
Modelo de Comunicación / Escalación
A continuación, se describe el modelo de comunicación y 
escalamiento de CFOTech:
En base a nuestra experiencia, el gráfico establece como se 
gestiona la comunicación entre el equipo de Cliente y 
CFOTech. Esto incluye tanto la comunicación formal como 
reuniones planificadas, informes de estado
y documentos de proyecto, como la comunicación informal 
como correos electrónicos, chats, llamadas telefónicas, etc.
También establecemos el modelo de escalamiento donde los 
problemas se pueden llevar desde el nivel de equipo hasta el 
nivel
de gestión según sea necesario.
40

[[página 41]]
Framework DevSecOps
Desde CFOTech priorizamos la Calidad, la Seguridad y la Agilidad. Por eso implementamos desde nuestros COEs, un framework estándar de DevSecOps.
41

[[página 42]]
IA en el ciclo de desarrollo
También nos apoyamos en las últimas 
tecnologías y tendencias para asegurar 
un mejor servicio.
Definimos el uso de herramientas 
complementarias para el desarrollo de 
software.
Nos apoyamos en Windsurf y Claude AI 
para mejorar y optimizar nuestro ciclo 
de desarrollos de software.
También contamos con nuestra propia 
herramienta de generación de casos de 
prueba Infinity Wizard.
42

[[página 43]]
Las responsabilidades que tendrá 
CFOTech serán las siguientes:
• Se realizarán reuniones periódicas entre el Delivery Manager y Gerente 
de Cliente con el fin de monitorear el proyecto.
• Se realizarán las ceremonias semanales entre el equipo de CFOTech y el 
Product Owner de Cliente para la revisión y priorización del backlog.
• El equipo asignado al proyecto desarrollará y realizará las pruebas 
unitarias e integrales de las funcionalidades priorizadas en el backlog.
• Acompañará junto a los key user de Cliente las pruebas de UAT.
• Realizará el diseño y la configuración de los ambientes (Dev, UAT)
43

[[página 44]]
Las responsabilidades que tendrá 
Cliente serán las siguientes:
44
• Proveerá y adquirirá para los ambientes de DEV, UAT y Prod,  la infraestructura, 
licencias, accesos a las bases de datos, herramientas y entornos necesarios para llevar a 
cabo el proyecto.
• Proveerá las historias de usuario posibles para cada funcionalidad a desarrollar.
• El cliente deberá gestionar y proveer los certificados a las Apis o WS que permiten el 
acceso a las distintas aplicaciones de terceros que se utilicen en las integraciones 
incluidas en la propuesta.
• El cliente asignará el personal necesario con los conocimientos de negocio, técnicos y la 
capacidad de decisión que permitan el correcto avance del proyecto.
• Entregará los permisos y accesos que requiera el personal de CFOTech asignado al 
proyecto para  todos los ambientes (DEV, UAT) en la nube del Cliente.
• Para las integraciones con sistemas de terceros, de no contar con ambientes de prueba 
(Dev / UAT) será responsabilidad del cliente proveer los Set de Datos para realizar las 
pruebas en cada ambiente.
• Realizará le implementación de la plataforma en el ambiente de Producción y configuraciones 
necesarias según sus estándares

[[página 45]]
Consideraciones generales:
• Quedan fuera de alcance cualquier funcionalidad que no se encuentre descripta en este documento.
• Se asume que el cupón de acceso tiene fecha de vencimiento y cantidad máxima de usos 
configurables de forma independiente por alianza. Ambos parámetros son obligatorios al dar de alta 
una alianza.
• Se asume que el cupón de cada alianza puede ser utilizado por distintos clientes (no es de uso único 
por persona). Si el cupón está vencido o con usos agotados, se muestra un mensaje de error genérico 
al cliente final. No se contempla personalización en el contenido del mensaje de error por alianza. 
• La plataforma no contempla la gestión o  registración de los reiterados contactos con clientes o ventas 
realizadas ni procesos incluidos en CRM. 
• Asumimos que todas la Apis provistas por Supervielle, contaran con los datos de Alianza, y Cupón de 
beneficios.
• La posibilidad de que el cupón de acceso de la alianza lleve asociado un beneficio comercial aplicable 
durante la cotización (por ejemplo, un descuento sobre el valor de la prima, una cobertura adicional sin 
costo u otro beneficio promocional) queda pendiente de definición durante la etapa de Inception. 
• El Look & Feel será definido entre CFOTech y el PO del Cliente.
• Una vez recibida la aprobación de la presente propuesta se estiman 30 días para el inicio del proyecto.
• La propuesta  no considera servicio de soporte post-implementación.
• El servicio será brindado de forma remota los días hábiles en el horario de Lunes a Viernes de 9 a 18 
horas.
• La propuesta no considera material de capacitación y dictado de talleres de capacitación.
• Si hiciesen falta horas adicionales las mismas serán acordadas previo a su ejecución, las que luego 
serán incluidas en la facturación mensual.
• De requerirse horas extras fuera del horario normal, las mismas serán compensadas considerando 
cuando fueron realizadas. En el caso que no fuese posible serán compensadas se acordará su 
facturación.
45

[[página 46]]
Consideraciones técnicas:
• La seguridad de la Solución estará alineada con los estándares de WASP (https://owasp.org/)
• En caso de utilizarse SonarQube para análisis de código o cualquiera de sus funcionalidades la licencia 
deberá ser abonada por el cliente.
• En la etapa de Inception del proyecto se ajustarán las estimaciones realizadas en función de los 
cambios de alcance o complejidad que se detecten al realizar el relevamiento detallado del backlog de 
funcionalidades a priorizar.
• En caso de no recibir el equipo de CFOTech la infraestructura solicitada para la creación de los 
ambientes y los permisos necesarios de parte del Cliente , se verán afectados los plazos de entrega de 
esta propuesta
• En caso de tener que utilizar algún servicio de email en la aplicación se utilizará un servicio que tenga el 
cliente.
• Según se indico en la documentación del Cliente queda fuera de alcance la implementación de los
endpoints de descarga de póliza (broker y aseguradora), 
• A la fecha de esta propuesta, no se dispone de la documentación técnica de las APIs. Por tanto, la 
estimación de integraciones se basa en supuestos estándar de la industria. Cualquier complejidad 
técnica no declarada será evaluada durante la etapa de Inception en donde se espera recibir la 
documentación técnica necesaria, lo que podría derivar en un ajuste del alcance o del esfuerzo 
estimado.
• Se especificaron los perfiles que SUPERVIELLE asignará al proyecto, manteniendo la metodología de 
trabajo (Inception desk + Agile), donde consideramos que los equipos tanto de SUPERVIELLE como 
CFOTECH participarán en cada etapa dependiendo de la instancia en la que se encuentre el proyecto.
46

[[página 47]]
El contenido generado por IA puede ser incorrecto.
¡Muchas
gracias!
Esperamos poder construir soluciones juntos.
www.cfotechlatam.com
47
