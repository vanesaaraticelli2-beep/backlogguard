---
name: auditoria-de-alcance
description: "Cómo comparar lo tratado en las reuniones con lo vendido en la preventa y clasificar los hallazgos."
metadata:
  course-version: "1"
  course-role: auditor
---
# Auditoría de alcance

El expediente ya viene calculado por el sistema («precalculada»): no lo repitas. Leelo y emití el informe. Solo volvé a llamar a una tool si necesitás otro parámetro (por ejemplo más coincidencias por punto).
- `consultar_decisiones_vigentes`: qué ya está decidido y aprobado. No lo vuelvas a plantear como problema.
- `comparar_con_preventa`: los puntos de la preventa, las reuniones, los ítems del tablero y las coincidencias más parecidas. La similitud solo ayuda a ordenar: leé los textos y juzgá vos.
- `detectar_contradicciones`: pares de fragmentos parecidos, con fecha y orador. Decidí si son una evolución o una contradicción.

## Tipos de hallazgo (`kind`)
- `vendido_no_tratado`: algo de la preventa que ninguna reunión trata.
- `tratado_no_vendido`: algo que las reuniones piden y la preventa no incluía.
- `cambio_de_alcance`: el trabajo crece o cambia respecto de lo vendido (por ejemplo, una funcionalidad nueva). Va con `tratado_no_vendido` cuando corresponde.
- `decision_evolucionada`: la misma persona o autoridad cambió de postura en una reunión posterior. La versión nueva reemplaza a la vieja. Poné `item_id` SOLO si un ítem del tablero quedó con la versión vieja.
- `contradiccion`: dos posturas incompatibles sin que una reemplace a la otra (por ejemplo, de interlocutores distintos el mismo día).

## Cómo informar
- Cada hallazgo lleva al menos una cita: el `chunk_id` y una frase textual de ese fragmento. Si compara dos fuentes, citá ambas.
- No inventes hallazgos. Si algo está bien cubierto, no lo informes.
