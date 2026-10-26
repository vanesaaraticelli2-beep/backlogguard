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
3. Con `redactar_historia` creá un ítem por requisito. Una historia lleva descripción "Como … quiero … para …" y uno o más criterios Gherkin con la forma `Dado … Cuando … Entonces …`.

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
