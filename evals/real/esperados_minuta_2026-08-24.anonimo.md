# Respuestas esperadas · Minuta 24-08-2026 (LogiCorp · Elecciones DMS)

BORRADOR propuesto por Claude a partir del PDF. Falta tu revisión: tachá lo que sobre, corregí lo que esté mal y agregá lo que falte.
Este archivo no se versiona (`evals/real/` está en .gitignore).

## A. Requisitos que deberían salir (21)
| # | Requisito esperado | Acuerdo / tema |
|---|---|---|
| 1 | Cada elección es un ambiente lógico aislado | A#1 · T1 |
| 2 | Dos perfiles: Super Admin (vista consolidada) y Admin (una elección) | A#2 · T1 |
| 3 | El Admin puede crear una elección pero solo ve la que creó | A#3 · T1 |
| 4 | Sin candado: los datos de la elección se editan hasta último momento | A#4 · T1 |
| 5 | Carta Marina: carga masiva solo por Excel (circuito, sección, mesa, establecimiento) | T2 |
| 6 | Limpieza y preparación del Excel fuera del sistema; el sistema solo mapea columnas y persiste | A#5 · T2 |
| 7 | Cada carga borra lo anterior de esa elección y escribe limpio | A#6 · T2 |
| 8 | Ícono de lápiz para editar un campo de la grilla sin re-subir el Excel | A#7 · T2 |
| 9 | Bloquear la carga si se repite ID de Escuela + Código de Mesa, e indicar la fila | A#8 · T2 |
| 10 | Maestro de autoridades: DNI obligatorio y único; ningún otro campo obligatorio | T4 |
| 11 | Roles de autoridades configurables por elección (panel en «Datos de elección») | T4 |
| 12 | Tres campos de contrato obligatorios en el alta de elección (Notificaciones, Distribución de Urnas, Material Electoral) | A#10 · T4 |
| 13 | Integración por API con el TMS (DNI + Contrato): número de envío y estado | A#11 · T4 |
| 14 | Actualización automática de estados dos veces al día | A#11 · T4 |
| 15 | Historial cronológico de hasta 3 notificaciones por DNI | A#12 · T4 |
| 16 | Autoridades por Lotes (importación progresiva sin borrar lotes previos) | A#13 · T4 |
| 17 | Pagos: carga masiva de órdenes del tribunal por Excel (DNI, Nombre, Monto) con mapeo dinámico por elección | T5 |
| 18 | El monto es solo un campo informativo; sin fórmulas de viáticos | A#15 · T5 |
| 19 | Conciliación: presentismo en tres cortes + autogestión QR (CBU/Alias), cruzado con las órdenes | T5 |
| 20 | Comprobantes: carga masiva de un ZIP con PDFs individuales | A#17 · T5 |
| 21 | Correo con enlace al portal solo si la autoridad ya tiene su comprobante cargado | A#18 · T5 |

## B. Fuera del alcance (no deben salir como historias)
- Plantillas de impresión, impresión centralizada y emisión física de notificaciones (A#14).
- Operación del sábado: armado y despacho de urnas e insumos (T3).

## C. Pendientes / sin definir (deben marcarse como abiertos, no como requisitos firmes)
- Maestro de Materiales: standby, a confirmar por LogiCorp (A#9).
- Integración con pasarelas de pago o bancos: a confirmar por LogiCorp (A#16).
- Regla de nomenclatura de los PDF para mapear comprobantes (A#17).

## D. Inconsistencias que debería detectar (propuestas, a validar)
1. El Tema #3 se titula «Fuera de Alcance», pero el texto dice que el Maestro de Materiales queda en standby. Además el Acuerdo #9 lo deja en espera. No está cerrado.
2. El Acuerdo #10 exige como obligatorios el «Contrato de Distribución de Urnas» y el «Contrato de Material Electoral», mientras el armado y despacho de urnas y el Maestro de Materiales están fuera o en standby.
3. Los acuerdos #17 y #18 dependen de una nomenclatura que está pendiente: el requisito 20 no se puede cerrar y el 21 depende de él.

## E. Ruido que NO debe volverse requisito
- Marcas sueltas como «[70, 72, 73, 77]» y «[84]».
- Indicaciones sobre Figma y los próximos pasos con fecha «A definir».
- Ejemplos (Chaco con más de 7 elecciones, «mesa 1 a 5»).

## F. Qué no puedo evaluar todavía
Contradicciones contra la preventa y cambios de alcance entre reuniones: necesito la preventa y al menos una segunda minuta.
