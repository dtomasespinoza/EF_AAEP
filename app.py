"""
 app.py
 ======

 Adaptador WEB de RAPPIDOS. Es la entrada de la interfaz grafica.

 Este archivo es un ADAPTADOR: no contiene reglas de negocio. Todo lo que
 hace es traducir peticiones HTTP en llamadas al nucleo, y resultados del
 nucleo en respuestas HTTP. Se comprueba viendo que aqui no hay ni un solo
 `if` sobre el peso de un pedido ni una sola comparacion de algoritmos:
 toda la logica vive en `nucleo/`.

 Dos estilos de ruta conviven a proposito:

    - RUTAS DE PAGINA: devuelven HTML con Jinja2. Son las que ve la persona.
    - RUTAS DE API: devuelven JSON y las consume el JavaScript de la pagina.

    La API existe para que el JavaScript pueda actualizar una tabla o un
    grafico sin recargar la pagina entera.

 Ejecucion:  python app.py
"""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Response, jsonify, render_template, request, send_file

from nucleo import RAPPIDOS
from nucleo.importador import plantilla_csv
from nucleo.modelos import (
    CAPACIDAD_VEHICULO_KG,
    CampoOrden,
    EstrategiaOrden,
    EstrategiaReparto,
)
from nucleo.reparto import ObjetivoMochila
from nucleo.serializador import respuesta, serializar

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "interfaz" / "web" / "templates"),
    static_folder=str(BASE_DIR / "interfaz" / "web" / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["JSON_SORT_KEYS"] = False

servicio = RAPPIDOS()

#: Importaciones que el usuario todavia NO ha confirmado.
#:
#: Es lo que hace posible el flujo en dos pasos que pidio el equipo: al subir
#: el archivo se devuelve una vista previa con un token, y nada se guarda
#: hasta que se confirma.
#:
#: El token es NECESARIO y no un adorno. Si el navegador mandara la lista de
#: pedidos a confirmar, cualquiera con curl podria confirmar una carga
#: arbitraria, o confirmarla dos veces. Guardando la vista previa en el
#: servidor, el cliente solo puede decir "confirma el token X": el contenido
#: real lo decide el nucleo. El token se borra al confirmarlo, de modo que
#: un token no se puede reutilizar para cargar dos veces el mismo archivo.
importaciones_pendientes: Dict[str, Any] = {}


# --------------------------------------------------------------------------
# Utilidades de la capa web
# --------------------------------------------------------------------------


def _json(datos) -> Response:
    """Devuelve un JSON con el sobre estandar de la API."""
    return jsonify(respuesta(True, "", datos))


def _error(mensaje: str, codigo: int = 400):
    """Devuelve un error con el mismo sobre, para que el cliente no distinga."""
    return jsonify(respuesta(False, mensaje, None)), codigo


def _dato(nombre: str, por_defecto=None):
    """Lee un dato del cuerpo de la peticion, o de la URL en los GET.

    Hay que mirar las tres fuentes porque Flask las separa: un `<form>`
    normal o un `POST` con JSON mandan el cuerpo, mientras que un
    `GET /api/pedidos?orden=QUICKSORT` manda los parametros en la query
    string. Sin `args`, los filtros del listado se ignorarian en silencio y
    la pagina siempre devolveria lo mismo.
    """
    if request.is_json:
        datos = request.get_json(silent=True, force=True) or {}
        return datos.get(nombre, por_defecto) if isinstance(datos, dict) else por_defecto

    if nombre in request.form:
        return request.form[nombre]

    return request.args.get(nombre, por_defecto)


def _decimal(nombre: str, por_defecto=None):
    """Lee un numero del cuerpo de la peticion, o None si no es valido."""
    crudo = _dato(nombre)

    if crudo is None or str(crudo).strip() == "":
        return por_defecto

    try:
        return float(str(crudo).replace(",", ".").strip())
    except (TypeError, ValueError):
        return por_defecto


def _texto(nombre: str, por_defecto: str = "") -> str:
    valor = _dato(nombre)
    return por_defecto if valor is None else str(valor).strip()


def _estrategia_reparto() -> EstrategiaReparto:
    """Interpreta el parametro de estrategia de reparto de la peticion."""
    try:
        return EstrategiaReparto(_texto("estrategia", "PRIMERO_QUE_CABE").upper())
    except ValueError:
        return EstrategiaReparto.PRIMERO_QUE_CABE


def _estrategia_orden() -> EstrategiaOrden:
    """Interpreta el parametro de estrategia de ordenamiento."""
    try:
        return EstrategiaOrden(_texto("orden_algoritmo", "QUICKSORT").upper())
    except ValueError:
        return EstrategiaOrden.QUICKSORT


def _objetivo() -> str:
    """Interpreta el objetivo de la mochila 0/1, con un valor seguro."""
    valor = _texto("objetivo", ObjetivoMochila.CANTIDAD).upper()

    if valor not in (ObjetivoMochila.CANTIDAD, ObjetivoMochila.PESO):
        return ObjetivoMochila.CANTIDAD

    return valor


def _campo_orden() -> CampoOrden:
    """Interpreta por que campo se quiere ordenar la tabla de pedidos.

    Un valor desconocido cae en PESO, que es el orden por defecto del
    sistema y el unico que aplica un algoritmo de los del curso.
    """
    try:
        return CampoOrden(_texto("campo", "PESO").upper())
    except ValueError:
        return CampoOrden.PESO


def _viajes() -> int:
    """Cantidad de viajes del plan. `0` significa "los que hagan falta"."""
    try:
        return max(int(_texto("viajes", "0") or 0), 0)
    except ValueError:
        return 0


# ==========================================================================
# PAGINAS
# ==========================================================================


@app.route("/")
def pagina_inicio():
    """Panel principal: resumen y acceso rapido a registrar."""
    return render_template("inicio.html", activo="inicio", capacidad=CAPACIDAD_VEHICULO_KG)


@app.route("/pedidos")
def pagina_pedidos():
    """Listado con buscador, filtros y comparador de algoritmos."""
    return render_template("pedidos.html", activo="pedidos", capacidad=CAPACIDAD_VEHICULO_KG)


@app.route("/carga")
def pagina_carga():
    """Carga masiva por archivo, con vista previa y confirmacion."""
    return render_template("carga.html", activo="carga", capacidad=CAPACIDAD_VEHICULO_KG)


@app.route("/salidas")
def pagina_salidas():
    """Planificacion de uno o varios viajes y comparacion de estrategias."""
    return render_template("salidas.html", activo="salidas", capacidad=CAPACIDAD_VEHICULO_KG)


@app.route("/analisis")
def pagina_analisis():
    """Analisis: comparacion de algoritmos y busqueda de pedidos.

    Antes estas herramientas vivian repartidas entre el menu de Pedidos y el
    de Salidas. El equipo pidio reunirlas bajo un mismo apartado de
    Analisis, asi que la comparacion y la busqueda se cargan aqui con un
    enlace directo desde los menus donde estaban.
    """
    return render_template("analisis.html", activo="analisis", capacidad=CAPACIDAD_VEHICULO_KG)


@app.route("/estadisticas")
def pagina_estadisticas():
    """Metricas del sistema y graficas."""
    return render_template("estadisticas.html", activo="estadisticas", capacidad=CAPACIDAD_VEHICULO_KG)


# ==========================================================================
# API: PEDIDOS
# ==========================================================================


@app.route("/api/pedidos", methods=["GET"])
def api_listar():
    """Lista pedidos con filtros de peso y distrito, y orden opcional.

    `campo` decide POR QUE se ordena y `orden_algoritmo` decide COMO, que no
    es lo mismo: los algoritmos de ordenamiento del curso solo tienen sentido
    sobre el peso. Pedir ordenarlos por codigo con QuickSort no significaria
    nada, asi que en ese caso el nucleo usa el comparador nativo.
    """
    try:
        estrategia = EstrategiaOrden(_texto("orden_algoritmo", "").upper())
    except ValueError:
        estrategia = None

    pedidos = servicio.listar(
        peso_min=_decimal("peso_min"),
        peso_max=_decimal("peso_max"),
        solo_pendientes=_texto("solo_pendientes", "1") not in ("0", "false", "no", ""),
        orden=estrategia,
        descendente=_texto("descendente", "0") in ("1", "true", "si", "sí"),
        campo=_campo_orden(),
        distrito=_texto("distrito") or None,
    )

    return _json({
        "pedidos": [p.a_dict() for p in pedidos],
        "total": len(pedidos),
    })


@app.route("/api/pedidos", methods=["POST"])
def api_registrar():
    """Registra un pedido individual."""
    resultado = servicio.registrar(
        peso=_dato("peso"),
        direccion=_texto("direccion"),
        cliente=_texto("cliente"),
        telefono=_texto("telefono"),
        distrito=_texto("distrito"),
    )

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json({"pedido": serializar(resultado.datos)})


@app.route("/api/pedidos/editar-masivo", methods=["POST"])
def api_editar_masivo():
    """Corrige varios pedidos en una sola operacion.

    El equipo pidio edicion masiva porque corregir 40 pedidos a mano era
    inviable. Los codigos llegan en `codigos`, que puede venir como una lista
    JSON o como texto separado por comas: el formulario lo rellena JavaScript
    con un array, pero permitir el texto hace que la ruta tambien se pueda
    probar con curl sin construir JSON.
    """
    codigos = _dato("codigos") or []

    if isinstance(codigos, str):
        codigos = [parte.strip() for parte in codigos.split(",") if parte.strip()]

    resultado = servicio.editar_masivo(
        codigos=codigos,
        peso=_dato("peso"),
        distrito=_texto("distrito") or None,
        cliente=_texto("cliente") or None,
    )

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json({
        "mensaje": resultado.mensaje,
        "pedidos": [p.a_dict() for p in resultado.datos or []],
    })


@app.route("/api/pedidos/<codigo>", methods=["PUT", "POST"])
def api_editar(codigo: str):
    """Corrige un pedido ya registrado.

    Acepta `PUT` y `POST` porque el metodo HTTP correcto para una edicion es
    PUT, pero algunos clientes y formularios antiguos solo saben hacer POST.
    Admitir los dos evita un 405 que no explicaria nada al usuario.
    """
    resultado = servicio.editar(
        codigo=codigo,
        peso=_dato("peso"),
        direccion=_dato("direccion"),
        cliente=_dato("cliente"),
        telefono=_dato("telefono"),
        distrito=_dato("distrito"),
    )

    if not resultado.ok:
        return _error(resultado.mensaje, 404 if "No existe" in resultado.mensaje else 400)

    return _json({"pedido": serializar(resultado.datos)})


@app.route("/api/pedidos/<codigo>", methods=["DELETE"])
def api_eliminar(codigo: str):
    """Elimina un pedido de forma definitiva."""
    resultado = servicio.eliminar(codigo)

    if not resultado.ok:
        return _error(resultado.mensaje, 404)

    return _json({"codigo": codigo.upper()})


@app.route("/api/pedidos/<codigo>/reabrir", methods=["POST"])
def api_reabrir(codigo: str):
    """Devuelve un pedido despachado a la lista de pendientes."""
    resultado = servicio.devolver_a_pendientes(codigo)

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json({"pedido": serializar(resultado.datos)})


@app.route("/api/pedidos/<codigo>/priorizar", methods=["POST"])
def api_priorizar(codigo: str):
    """Devuelve el plan de carga forzando ese pedido como prioritario.

    Se apoya en la busqueda binaria: el codigo se normaliza a mayusculas y
    se localiza en la lista ordenada, de modo que la interfaz no tiene que
    saber si el pedido existe ni si hay otros iguales.
    """
    resultado = servicio.buscar(codigo)

    if not resultado.ok:
        return _error(resultado.mensaje, 404)

    encontrado = resultado.datos["pedido"]

    if not encontrado.pendiente:
        return _error(f"El pedido {encontrado.codigo} ya fue despachado.")

    plan = servicio.planear_carga(
        viajes=1,
        estrategia=_estrategia_reparto(),
        prioritario=encontrado.codigo,
        objetivo=_objetivo(),
    )

    if not plan.ok:
        return _error(plan.mensaje)

    return _json(serializar(plan.datos))


# ==========================================================================
# API: BUSQUEDA Y ALGORITMOS
# ==========================================================================


@app.route("/api/buscar", methods=["POST"])
def api_buscar():
    """Busca un pedido por codigo con busqueda binaria o lineal."""
    resultado = servicio.buscar(
        _texto("codigo"),
        usar_binaria=_texto("algoritmo", "BINARIA").upper() != "LINEAL",
    )

    if not resultado.ok:
        return _error(resultado.mensaje, 404)

    return _json(serializar(resultado.datos))


@app.route("/api/buscar/comparar", methods=["POST"])
def api_buscar_comparar():
    """Ejecuta la busqueda con ambos algoritmos y contrasta el coste."""
    resultado = servicio.buscar_codigo_por_algoritmo(_texto("codigo"))

    if not resultado.ok:
        return _error(resultado.mensaje, 404)

    return _json(serializar(resultado.datos))


@app.route("/api/algoritmos", methods=["GET"])
def api_algoritmos():
    """Mide todos los algoritmos de ordenamiento sobre los pendientes."""
    resultado = servicio.comparar_algoritmos(_estrategia_orden())

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json(serializar(resultado.datos))


# ==========================================================================
# API: CARGA MASIVA
# ==========================================================================


@app.route("/api/carga/archivo", methods=["POST"])
def api_importar():
    """Analiza un archivo CSV, TXT o XLSX y devuelve una VISTA PREVIA.

    No registra nada. La respuesta incluye un `token` que hay que mandar a
    `/api/carga/confirmar` para que los pedidos se guarden de verdad. Ese
    paso en dos tiempos es lo que pidio el equipo: subir un archivo ya no
    mete pedidos en el sistema sin que nadie los revise antes.
    """
    archivo = request.files.get("archivo")

    if archivo is None or not archivo.filename:
        return _error("No se selecciono ningun archivo.")

    # El limite de tamano lo impone Flask antes de leer el archivo, para no
    # agotar la memoria. Este mensaje traduce el error 413.
    if archivo.content_length is not None and archivo.content_length > app.config["MAX_CONTENT_LENGTH"]:
        return _error("El archivo supera el maximo permitido de 16 MB.")

    resultado = servicio.importar(archivo.filename, archivo.read())

    if not resultado.ok:
        return _error(resultado.mensaje)

    token = uuid.uuid4().hex
    importaciones_pendientes[token] = resultado.datos

    return _json({
        "token": token,
        "mensaje": resultado.mensaje,
        "vista_previa": serializar(resultado.datos),
    })


@app.route("/api/carga/confirmar", methods=["POST"])
def api_confirmar_importacion():
    """Registra los pedidos de una vista previa ya revisada.

    El token se busca en el diccionario del servidor y se BORRA despues, tanto
    si la confirmacion tuvo exito como si fallo. Borrarlo siempre es lo que
    impide confirmar dos veces la misma subida y duplicar los pedidos.
    """
    token = _texto("token")

    if not token:
        return _error("Falta el token de confirmacion.")

    vista_previa = importaciones_pendientes.pop(token, None)

    if vista_previa is None:
        return _error(
            "Esa importacion ya se confirmo o expiro. Vuelve a subir el archivo.", 404
        )

    resultado = servicio.confirmar_importacion(vista_previa)

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json({
        "mensaje": resultado.mensaje,
        "pedidos": [p.a_dict() for p in getattr(vista_previa, "pedidos", [])],
    })


@app.route("/api/carga/plantilla", methods=["GET"])
def api_plantilla():
    """Descarga un CSV de ejemplo para que el usuario vea el formato."""
    return send_file(
        io.BytesIO(plantilla_csv().encode("utf-8")),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name="plantilla_rappidos.csv",
    )


# ==========================================================================
# API: SALIDAS
# ==========================================================================


@app.route("/api/salidas/plan", methods=["POST"])
def api_plan():
    """Simula un plan de carga SIN despachar nada.

    Permite planear uno o varios viajes: `viajes=0` significa "todos los que
    hagan falta". La respuesta es un PlanCarga completo, con detalle de cada
    viaje y de lo que no asigno.
    """
    resultado = servicio.planear_carga(
        viajes=_viajes(),
        estrategia=_estrategia_reparto(),
        prioritario=_texto("prioritario") or None,
        objetivo=_objetivo(),
    )

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json(serializar(resultado.datos))


@app.route("/api/salidas/confirmar", methods=["POST"])
def api_confirmar():
    """Confirma el plan (uno o varios viajes) y despacha sus pedidos.

    Se vuelve a planificar para que el servidor sea la unica fuente de
    verdad: nunca se confia en la lista que envie el navegador. Esa medida
    evita que alguien manipule el cliente y despache pedidos al margen del
    plan.
    """
    plan = servicio.planear_carga(
        viajes=_viajes(),
        estrategia=_estrategia_reparto(),
        prioritario=_texto("prioritario") or None,
        objetivo=_objetivo(),
    )

    if not plan.ok:
        return _error(plan.mensaje)

    resultado = servicio.confirmar_carga(plan.datos)

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json({
        "mensaje": resultado.mensaje,
        "salida": serializar(resultado.datos),
    })


@app.route("/api/salidas/historial", methods=["GET"])
def api_historial():
    """Historial de salidas ya confirmadas.

    Cada salida conserva `detalle` (pedido por pedido, con distrito, viaje y
    datos originales). Ademas de la lista, se devuelve el detalle completo
    para mostrarlo cuando el usuario seleccione una salida en la web.
    """
    salidas = []
    for salida in servicio.historial():
        datos = salida.a_dict() if hasattr(salida, "a_dict") else {
            "id": salida.id,
            "fecha": salida.fecha,
            "cantidad": salida.cantidad,
            "peso_total": salida.peso_total,
            "capacidad": salida.capacidad,
            "viajes": getattr(salida, "viajes", 1),
            "estrategia": salida.estrategia,
            "prioritario": salida.prioritario,
            "codigos": salida.codigos,
            "detalle": getattr(salida, "detalle", []),
        }
        if "ocupacion" not in datos:
            viajes = max(int(datos.get("viajes") or 1), 1)
            capacidad_total = datos.get("capacidad", CAPACIDAD_VEHICULO_KG) * viajes
            datos["ocupacion"] = round(
                datos.get("peso_total", 0.0) / capacidad_total * 100, 1
            ) if capacidad_total > 0 else 0.0
        salidas.append(datos)

    return _json({"salidas": salidas})


@app.route("/api/salidas/<int:identificador>", methods=["GET"])
def api_detalle_salida(identificador: int):
    """Devuelve el detalle de una salida concreta.

    Esto cumple lo que pidio el equipo: despues de confirmar varias
    mochilas, se debe poder mostrar la carga de cada mochila. La respuesta
    trae el detalle completo (cada pedido con su viaje, distrito, direccion,
    cliente y telefono).
    """
    resultado = servicio.detalle_salida(identificador)

    if not resultado.ok:
        return _error(resultado.mensaje, 404)

    return _json(resultado.datos)


@app.route("/api/salidas/estrategias", methods=["GET"])
def api_comparar_estrategias():
    resultado = servicio.comparar_estrategias(_texto("prioritario") or None)
    if not resultado.ok:
        return _error(resultado.mensaje)
    return _json(serializar(resultado.datos))


# ==========================================================================
# API: ESTADISTICAS Y MANTENIMIENTO
# ==========================================================================


@app.route("/api/estadisticas", methods=["GET"])
def api_estadisticas():
    """Metricas y series para las graficas del panel."""
    resultado = servicio.estadisticas()

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json(serializar(resultado.datos))


@app.route("/api/limpiar", methods=["POST"])
def api_limpiar():
    """Vacia los pedidos pendientes, o todo el sistema."""
    resultado = servicio.limpiar(solo_pendientes=_texto("tipo", "pendientes") != "todo")

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json({"mensaje": resultado.mensaje})


@app.route("/api/catalogo", methods=["GET"])
def api_catalogo():
    """Enums y constantes que la interfaz necesita para construir sus menus.

    Se leen del codigo y no se escriben a mano en el JavaScript: si se anade
    una estrategia nueva en el nucleo, aparece en la interfaz sin tocar el
    front-end.
    """
    return _json({
        "capacidad": CAPACIDAD_VEHICULO_KG,
        "estrategias_reparto": [
            {
                "valor": estrategia.value,
                "etiqueta": estrategia.etiqueta,
                "descripcion": estrategia.descripcion,
            }
            for estrategia in EstrategiaReparto
        ],
        "algoritmos_orden": [
            {"valor": estrategia.value, "etiqueta": estrategia.etiqueta}
            for estrategia in EstrategiaOrden
        ],
        "objetivos": [
            {
                "valor": objetivo,
                "etiqueta": ObjetivoMochila.ETIQUETAS[objetivo],
            }
            for objetivo in (ObjetivoMochila.CANTIDAD, ObjetivoMochila.PESO)
        ],
    })


# ==========================================================================
# Manejo de errores
# ==========================================================================


@app.errorhandler(413)
def error_archivo_grande(excepcion):
    """Traduce el error 413 de Flask, que llega en ingles.

    OJO: el parametro NO se llama `_error`. Ese nombre es el de la funcion
    auxiliar que construye la respuesta JSON; si el parametro lo ocultara,
    la llamada de abajo invocaria la excepcion de Werkzeug en vez del
    constructor de la respuesta.
    """
    return _error("El archivo supera el maximo permitido de 16 MB.", 413)


@app.errorhandler(404)
def error_no_encontrado(excepcion):
    """Devuelve JSON si el cliente espera JSON, o la pagina 404 si no."""
    if request.path.startswith("/api/"):
        return _error("Endpoint no encontrado.", 404)

    return render_template("404.html"), 404


@app.errorhandler(500)
def error_servidor(error):
    """Evita filtrar detalles internos en la respuesta al cliente.

    El detalle si se escribe en la consola del servidor, donde si es util
    para depurar; al cliente solo se le dice que hubo un error.
    """
    app.logger.exception("Error no controlado: %s", error)
    return _error("Ocurrio un error interno. Revisa la consola del servidor.", 500)


if __name__ == "__main__":
    puerto = int(os.environ.get("PUERTO", "5000"))
    modo_depuracion = os.environ.get("MODO_DEBUG", "1") == "1"

    print("=" * 58)
    print("  RAPPIDOS - Sistema de pedidos")
    print(f"  Interfaz web en:  http://127.0.0.1:{puerto}")
    print(f"  Modo depuracion:  {'activo' if modo_depuracion else 'desactivado'}")
    print("=" * 58)

    app.run(host="127.0.0.1", port=puerto, debug=modo_depuracion)
