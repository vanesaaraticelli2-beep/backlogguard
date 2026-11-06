"""Arma evals/real/logicorp.json: las respuestas esperadas del caso real (anonimizado) en el formato de la evaluación.

Sale de los borradores evals/real/esperados_*.anonimo.md y de las tres minutas. Es un BORRADOR: lo valida la product owner.
Los grupos de palabras se comparan sin tildes ni mayúsculas y por contenido (una palabra puede ser parte de otra).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALCANCE = ["cambio_de_alcance", "vendido_no_tratado", "tratado_no_vendido", "decision_evolucionada", "contradiccion"]
CONTRADICCION = ["contradiccion", "decision_evolucionada", "cambio_de_alcance"]


def e(id_, texto, *grupos, tipo="", tipos=None):
    row = {"id": id_, "texto": texto, "grupos": [list(g) for g in grupos]}
    if tipo:
        row["tipo"] = tipo
    if tipos:
        row["tipos_aceptados"] = tipos
    return row


REQUISITOS = [
    # Minuta 24-08 (M1)
    e("R01", "Cada elección es un ambiente lógico aislado", ["eleccion", "aislad"], ["eleccion", "independiente"]),
    e("R02", "Dos perfiles: Super Admin (vista consolidada) y Admin (una elección)", ["super admin", "consolidad"], ["perfil", "super admin"]),
    e("R03", "El Admin puede crear una elección pero solo ve la que creó", ["admin", "crea", "solo"], ["visibilidad", "eleccion"]),
    e("R04", "Sin candado: los datos de la elección se editan hasta último momento", ["sin", "bloqueo", "eleccion"], ["edicion", "abierta"]),
    e("R05", "Carta Marina: carga masiva solo por Excel", ["carta marina", "excel", "carga"]),
    e("R06", "Limpieza del Excel fuera del sistema; el sistema solo mapea columnas y persiste", ["mapeo", "simple"], ["limpieza", "logicorp"]),
    e("R07", "Cada carga borra lo anterior de esa elección y escribe limpio", ["borr", "anterior"], ["reemplazo", "total"], ["escritura", "limpia"]),
    e("R08", "Ícono de lápiz para editar un campo sin volver a subir el Excel", ["lapiz"]),
    e("R09", "Bloquear la carga si se repite ID de Escuela + Código de Mesa, indicando la fila", ["duplicad", "escuela", "mesa"]),
    e("R10", "Maestro de autoridades: DNI obligatorio y único", ["dni", "autoridad", "unico"], ["dni", "autoridad", "obligatori"]),
    e("R11", "Roles de autoridades configurables por elección", ["roles", "autoridad"], ["rol", "configurable"]),
    e("R12", "Tres campos de contrato obligatorios en el alta de la elección", ["contrato", "obligatori"]),
    e("R13", "Integración por API con el TMS (DNI + Contrato)", ["tms", "api"]),
    e("R14", "Actualización automática de estados dos veces al día", ["dos veces"]),
    e("R15", "Historial cronológico de hasta 3 notificaciones por DNI", ["historial", "notificacion"]),
    e("R16", "Autoridades por lotes (importación progresiva)", ["lote"]),
    e("R17", "Pagos: carga masiva de órdenes del tribunal por Excel", ["orden", "pago", "excel"], ["tribunal", "excel"]),
    e("R18", "El monto es solo informativo; sin fórmulas de viáticos", ["monto", "informativo"], ["viatico"]),
    e("R19", "Conciliación: presentismo en tres cortes y autogestión QR, cruzado con las órdenes", ["presentismo"]),
    e("R20", "Comprobantes: carga masiva de un ZIP con PDF individuales", ["zip"]),
    e("R21", "Correo con enlace solo si la autoridad ya tiene su comprobante", ["comprobante", "correo"], ["notific", "pago", "comprobante"]),
    # Minuta 25-08 (M2)
    e("R22", "Mapa interactivo 2D de tráfico", ["mapa", "2d"]),
    e("R23", "Coordenadas precargadas desde la Carta Marina", ["coordenada", "carta marina"], ["latitud"]),
    e("R24", "Trazado de cobertura del nodo por polígono, con asociación automática", ["poligono", "nodo"]),
    e("R25", "Alta manual de nodo (título, descripción, dirección, geolocalización)", ["alta", "nodo"], ["formulario", "nodo"], ["crear", "nodo"]),
    e("R26", "Indicadores del nodo: establecimientos, urnas y radio", ["urnas", "nodo"], ["indicador", "nodo"]),
    e("R27", "El radio de cobertura es solo informativo", ["radio", "informativo"]),
    e("R28", "«Ver geolocalización» centra el mapa con un pin", ["pin"]),
    e("R29", "Asignación manual de establecimientos a nodos por desplegable", ["desplegable", "nodo"], ["asignacion manual", "establecimiento"]),
    e("R30", "Botón «Guardar y Confirmar», sin autoguardado", ["guardar y confirmar"], ["autoguardado"]),
    e("R31", "«Limpiar» borra solo el polígono elegido; sin «Deshacer»", ["limpiar"]),
    e("R32", "Candados de bloqueo de edición por módulo, solo para el Super Admin", ["candado"]),
    e("R33", "El backoffice solo recibe la nómina confirmada (reclutamiento externo)", ["nomina"], ["receptor"]),
    e("R34", "Nómina por Excel de columnas fijas, sin mapeo dinámico", ["columnas fijas"], ["estructura", "fija"]),
    e("R35", "Maestro de personal con DNI único y movilidad propia (SÍ/NO)", ["movilidad"]),
    e("R36", "Importación de personal acumulativa", ["acumulativ"]),
    e("R37", "Bajas individuales manuales en la grilla", ["baja", "manual"]),
    e("R38", "Se quita la columna «Estado» de la grilla de personal", ["columna", "estado"]),
    e("R39", "Bloqueo de la importación de personal por DNI duplicado o error de formato", ["dni", "duplicad", "formato"], ["dni", "duplicad", "personal"]),
    # Minuta 27-08 (M3)
    e("R40", "La tarea se compone de pasos secuenciales obligatorios", ["paso", "secuencial"]),
    e("R41", "Bloqueo por dependencias y franja horaria", ["dependencia"], ["franja", "horari"], ["tareas futuras"]),
    e("R42", "Categorías de tareas y alta de categoría desde la lista", ["categori", "tarea"]),
    e("R43", "El MVP se limita al personal de LogiCorp (sin transportistas)", ["transportista"]),
    e("R44", "Solo un rol administrador superior crea y edita tareas y templates", ["rol", "jerarquic"], ["administrador", "template"], ["restringid", "rol"]),
    e("R45", "Campos estándar (texto corto, largo, numérico)", ["texto corto"], ["campo", "numerico"]),
    e("R46", "Escaneo de DNI local y offline con sincronización en segundo plano", ["offline"], ["segundo plano"]),
    e("R47", "El template es la plantilla; la tarea es su instancia por elección", ["template", "instancia"], ["tarea", "template", "elecc"]),
    e("R48", "Repositorio global de templates y copia local por elección", ["repositorio", "global"], ["clon", "template"]),
]

OPCIONALES = [
    e("O01", "Autocompletado por escaneo de DNI con campo editable para corregir el OCR", ["ocr"]),
    e("O02", "Escaneo limitado a DNI argentino válido", ["dni argentino"], ["extranjero"]),
    e("O03", "Maestro de Materiales en standby (abierto, no firme)", ["material"]),
    e("O04", "Pasarelas de pago o bancos a confirmar (abierto)", ["pasarela"], ["banco"]),
    e("O05", "Nomenclatura de los PDF de comprobantes, pendiente", ["nomenclatura"]),
    e("O06", "Alcance del MVP limitado a la operativa del domingo", ["domingo", "mvp"]),
]

HALLAZGOS = [
    e("A1", "Rutas, recorridos y optimizador de flota vendidos; M2 los deja fuera del MVP", ["ruta", "recorrido"], tipo="cambio de alcance", tipos=ALCANCE),
    e("A2", "Material electoral vendido; M1/M2 lo dejan en standby o fuera", ["material"], tipo="cambio de alcance", tipos=ALCANCE),
    e("A3", "Reclutamiento, bot y alta de PA vendidos; M2: reclutamiento externo, solo se recibe la nómina", ["reclutamiento"], ["nomina"], tipo="cambio de alcance", tipos=ALCANCE),
    e("A4", "Asignación de PA por IA vendida; M2 la deja para otra tarjeta, solo manual", ["asignacion", "ia"], ["asignacion automatica"], tipo="cambio de alcance", tipos=ALCANCE),
    e("A5", "Comprobantes: vendida la carga individual; M1 la reemplaza por un ZIP masivo", ["zip"], ["comprobante", "individual"], tipo="cambio de alcance", tipos=ALCANCE),
    e("A6", "Impresión y emisión de piezas vendidas; M1 las excluye del MVP", ["impresion"], tipo="cambio de alcance", tipos=ALCANCE),
    e("A7", "Seguimiento DMS con 8 estados en tiempo real vendido; M1: 5 estados, dos veces al día, clave DNI + contrato", ["dos veces"], ["tiempo real", "estado"], tipo="cambio de alcance", tipos=ALCANCE),
    e("B1", "La preventa ofrece replicar maestros para una nueva elección; M1 dice que cada elección se diseña desde cero", ["replic"], tipo="contradicción", tipos=CONTRADICCION),
    e("B2", "M1: sin candados, edición abierta. M2: candados por módulo del Super Admin", ["candado"], tipo="contradicción", tipos=CONTRADICCION),
    e("B4", "La preventa calcula la liquidación con Oracle HCM; M1: el sistema no calcula montos", ["oracle"], ["liquidacion"], ["monto", "calcul"], tipo="contradicción", tipos=CONTRADICCION),
    e("C2", "M1 exige contratos obligatorios de urnas y material, que están fuera o en standby", ["contrato", "urna"], tipo="inconsistencia", tipos=CONTRADICCION),
]

TOLERADAS = [
    e("T1", "M2 dice que el Maestro de Materiales quedó fuera; M1 lo dejó en standby (lo cubre A2)", ["material", "standby"]),
    e("T2", "La preventa limita el LLM a dos módulos pero lista tres", ["llm", "modulo"]),
    e("T3", "La preventa ofrece plantillas de nota pero la impresión es manual", ["plantilla", "nota"]),
    e("T4", "Comprobantes y correo dependen de una nomenclatura sin definir", ["nomenclatura"]),
    e("T5", "M2 A#1 dice «excluido» y «pendiente de confirmación» a la vez", ["excluid", "pendiente"]),
    e("T6", "Transportistas fuera del MVP (refuerza A3)", ["transportista"]),
    e("T7", "Replicar una elección es riesgoso, pero se clonan templates (a validar)", ["clon", "template"]),
    e("T8", "El algoritmo heredado de escaneo de DNI está obsoleto (pendiente)", ["algoritmo"], ["obsoleto"]),
]

VERDAD = {
    "nombre": "LogiCorp (real, anonimizado)",
    "descripcion": "BORRADOR a validar por la product owner. Preventa de TechPartner y minutas del 24-08, 25-08 y 27-08-2026. "
    "Fuente: evals/real/esperados_*.anonimo.md y las minutas en data_real/fuentes.",
    "nota_de_emparejamiento": "Un texto cumple un elemento si contiene todas las palabras de alguno de sus grupos (sin tildes ni mayúsculas). "
    "Regla determinística: no usa un modelo como juez.",
    "requisitos": REQUISITOS,
    "opcionales": OPCIONALES,
    "hallazgos": HALLAZGOS,
    "toleradas": TOLERADAS,
}

if __name__ == "__main__":
    path = ROOT / "evals" / "real" / "logicorp.json"
    path.write_text(json.dumps(VERDAD, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{path}: {len(REQUISITOS)} requisitos, {len(OPCIONALES)} opcionales, {len(HALLAZGOS)} hallazgos, {len(TOLERADAS)} toleradas")
