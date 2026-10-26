---
name: delegacion-de-tareas
description: "Cómo planificar una corrida: qué fuentes usar para redactar y cómo delegar al agente de Requerimientos."
metadata:
  course-version: "1"
  course-role: supervisor
---
# Delegación de tareas

1. Recibís el objetivo y la lista de fuentes disponibles (id, tipo, fecha, nombre).
2. Llamás a `delegar_tarea` con agent="requerimientos", task="redactar", las fuentes y una instrucción breve y concreta.
   - Elegí reuniones y minutas. La preventa NO se usa para redactar: es la referencia que usa el Auditor.
   - Si el objetivo pide cubrir todos los requisitos, repetilo en la instrucción; no inventes un número máximo de historias.
3. Opcionalmente delegás `revisar` al Crítico y `auditar` al Auditor con una nota. Esos pasos se ejecutan siempre, hayas delegado o no.
4. Terminás con `final` y una frase que resuma el plan.
