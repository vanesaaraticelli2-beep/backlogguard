---
name: redaccion-de-historias
description: "Cómo convertir lo acordado en reuniones en historias de usuario citadas: qué es un requisito, cuándo agrupar y cuándo separar, y cómo citar."
metadata:
  course-version: "1"
  course-role: requerimientos
---
# Redacción de historias

Procedimiento, en este orden:
1. Con `ingestar_y_fragmentar` indexá cada fuente que te indique el objetivo (por su `document_id`).
2. Con `buscar_en_fuentes` encontrá los fragmentos que respaldan cada requisito. Podés filtrar por tipo de fuente.
3. Con `redactar_historia` creá un ítem por requisito. Una historia lleva **Como, quiero y para por separado** (los tres campos `como`, `quiero` y `para` son obligatorios y no pueden quedar vacíos: sin ellos la herramienta rechaza la historia; la descripción se arma sola) y sus criterios de aceptación.

## Criterios de aceptación: todos los escenarios
- Identificá **todos** los escenarios que surgen de las fuentes de ese requisito, no solo el caso feliz: el camino normal, los errores y rechazos, los casos borde, las validaciones y las reglas que se mencionan. Leé el fragmento citado y los vecinos antes de escribir.
- **Al menos uno** va como escenario `Dado … Cuando … Entonces …`. Los demás pueden ser escenarios o una **regla verificable** en una frase («El campo acepta solo caracteres numéricos», «La pantalla muestra el botón Validar y la opción Reenviar código»).
- Cada criterio se puede comprobar con sí o no. No inventes escenarios: si algo no figura en las fuentes, no es un criterio; mencionalo en tu respuesta final como duda.
- No agrupes en un criterio escenarios distintos, y no repitas el mismo escenario con otras palabras.
- Una historia lleva **como máximo 12 criterios** (la herramienta rechaza más, y es el mismo tope que controla el Crítico). Si te pasás, uní los que verifican lo mismo; si de verdad son requisitos independientes con respaldo en las fuentes, decilo en tu respuesta final en vez de descartar criterios.

## Antes de entregar cada historia (lo que el Crítico objeta primero)
Repasá cada historia con esta lista; en la última corrida el Crítico objetó 28 de 33 en la primera ronda por estos motivos:
1. **Cada promesa tiene su criterio.** Si la descripción dice «asociar cada comprobante a su registro», hay un criterio que lo verifica.
2. **Cada dato concreto figura en una frase citada de la historia** (un botón, un campo, una clave, un plazo, un rol). Si lo viste en el contexto pero esa frase no está entre las citas, buscala con `buscar_en_fuentes` y agregala en `citations` (con su `chunk_id` y la frase textual), o sacá el dato del criterio.
3. **El rol del «Como» es el que nombran las fuentes.** No lo inventes ni lo generalices («administrador que carga…» si nadie lo dijo).
4. **Los casos que más se omiten:** el error o rechazo (qué se informa y a quién), volver a importar o reemplazar datos ya cargados, qué pasa si falta un dato o viene repetido, y quién puede hacerlo.
5. **Algo posterior que cambia lo pedido** (otra reunión que lo reemplaza): no lo redactes distinto por tu cuenta; mencionalo en tu respuesta final.

## Cuántas historias y de qué tamaño (no hay un número fijo)
- Primero recorré la reunión y pensá la lista de **requisitos distintos**: cosas que el usuario o el negocio necesitan. Una historia por requisito; el objetivo es cubrirlos todos.
- Varias frases que hablan de lo mismo son **un** requisito. Ejemplo: «conservar el historial de cada reintento de una factura», «saber cuántas veces fue reprocesada» y «cada intento queda como evento independiente» son la misma funcionalidad: no hacen tres historias.
- Separá en dos historias solo si cada una entrega un resultado distinto y visible para el usuario (por ejemplo, registrar el historial y, aparte, verlo en una línea de tiempo), o si una puede entregarse sin la otra. Al separar, que el título y la descripción de cada una hablen de SU resultado y no repitan la frase de la otra.
- El tamaño lo da la reunión: un tema con muchos casos puede ser una épica con varias historias; un detalle menor puede ser un criterio de aceptación de otra historia y no una historia.
- Cubrí todos los temas de la reunión antes de profundizar en uno solo. Un tema que se trató en pocas líneas igual es un requisito.

## No repetir lo ya redactado
- `buscar_en_fuentes` te devuelve en `ya_redactadas` lo que ya escribiste. Antes de redactar, mirá esa lista: si el requisito ya está, pasá al siguiente.
- Si `redactar_historia` te rechaza por posible duplicado, no lo reformules: seguí con otro requisito.

## Citar bien
- Citá con el `chunk_id` que devolvió la búsqueda y una frase textual de ese fragmento. No cites nada que no hayas recuperado.
- Las búsquedas viejas llegan resumidas (id, fuente y el comienzo del texto). Si necesitás citar un fragmento que ya no ves completo, buscalo de nuevo antes de citarlo.
- Una respuesta del cliente respalda un requisito; una pregunta del analista sola no. Citá la respuesta que lo confirma.
