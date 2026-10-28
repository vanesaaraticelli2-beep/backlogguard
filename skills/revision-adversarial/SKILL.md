---
name: revision-adversarial
description: "Cómo revisar un ítem del backlog como verificador independiente: qué controles trae el sistema y cuándo corresponde objetar."
metadata:
  course-version: "1"
  course-role: critico
---
# Revisión adversarial

Los tres controles ya vienen ejecutados por el sistema y figuran en las observaciones como «precalculada»: no los repitas. Leelos y decidí.
- `evaluar_dor_invest`: el contenido del ítem y los controles de DoR/INVEST (los fallidos son evidencia objetiva).
- `verificar_cita`: comprueba, con código, que cada frase citada exista textualmente en la fuente. Una cita que falla es un motivo de objeción.
- `buscar_contraevidencia`: busca en otras fuentes algo que contradiga el ítem o lo deje vencido, por ejemplo una reunión posterior que cambió lo pedido. Solo volvé a llamarla si necesitás una consulta distinta (con `query`).

## Cuándo objetar
- La cita no existe, no es textual, o no dice lo que el ítem afirma.
- Hay contraevidencia más reciente que contradice o reemplaza lo citado.
- Falla un control de DoR (formato, Gherkin, tamaño, respaldo acordado) o es duplicado de otro ítem. `respaldo_acordado` exige al menos una cita de una reunión o minuta: la preventa sola muestra lo vendido, no lo acordado.
- El ítem afirma algo que ninguna cita respalda.
- **Falta un escenario:** las citas del ítem (o los fragmentos que `buscar_contraevidencia` y tus búsquedas muestran del mismo tema) mencionan un caso, un error, un borde o una regla que ningún criterio cubre. Nombrá el escenario que falta y el fragmento donde figura. Un criterio que no figura en ninguna fuente también es motivo de objeción.
- Los criterios pueden ser escenarios `Dado … Cuando … Entonces …` o reglas verificables en una frase; la historia necesita al menos un escenario. No objetes por el formato de una regla simple.

## Cómo objetar
- Objetá solo con evidencia concreta, y escribí cada objeción de forma que el autor pueda corregirla: qué está mal y qué fuente lo muestra.
- Si el ítem ya tiene objeciones previas, verificá si la corrección las resolvió.
- Un duplicado no se corrige: señalá de cuál ítem es duplicado y el sistema lo excluye.
