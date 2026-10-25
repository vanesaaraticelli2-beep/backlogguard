# Especificaciones por agente

Cada especificación describe **qué debe cumplir** un agente, en lenguaje funcional, y enlaza cada requisito con el test que lo verifica. Sirve de contrato: si cambia un requisito, cambia primero la especificación y luego el código y el test.

| Agente | Estado | Especificación |
|---|---|---|
| Requerimientos (productor) | Implementado (Día 5) | [requerimientos.md](requerimientos.md) |
| Crítico | Implementado (Día 6) | [critico.md](critico.md) |
| Auditor de Proyecto | Implementado (Día 7) | [auditor.md](auditor.md) |
| Supervisor y grafo | Implementado (Día 8) | [supervisor.md](supervisor.md) |
| Integración | Pendiente (Día 9) | — |

Las de Requerimientos y Crítico se redactaron **después** de construirlos, a partir del código y los tests. La del Auditor se redactó **antes** de construirlo, y es la base de su plan; se ajustó al terminar.

## Cómo se lee cada especificación
- **Propósito:** para qué existe el agente.
- **Entradas y salidas:** qué recibe y qué devuelve, y con qué contrato Pydantic.
- **Requisitos:** reglas con identificador (`RQ-01`, `CR-01`, `AU-01`…), cada una con su test.
- **Fuera del curso:** decisiones propias que se apartan del contenido de las clases.
- **Límites conocidos:** lo que el agente no hace todavía.
