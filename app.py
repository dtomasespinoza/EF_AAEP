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
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file

from nucleo import RAPPIDOS
from nucleo.importador import plantilla_csv
from nucleo.modelos import CAPACIDAD_VEHICULO_KG, EstrategiaOrden, EstrategiaReparto
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
    """Carga masiva: generar al azar o subir archivo."""
    return render_template("carga.html", activo="carga", capacidad=CAPACIDAD_VEHICULO_KG)


@app.route("/salidas")
def pagina_salidas():
    """Planificacion de salida y comparacion de estrategias."""
    return render_template("salidas.html", activo="salidas", capacidad=CAPACIDAD_VEHICULO_KG)


@app.route("/estadisticas")
def pagina_estadisticas():
    """Metricas del sistema y graficas."""
    return render_template("estadisticas.html", activo="estadisticas", capacidad=CAPACIDAD_VEHICULO_KG)


# ==========================================================================
# API: PEDIDOS
# ==========================================================================


@app.route("/api/pedidos", methods=["GET"])
def api_listar():
    """Lista pedidos con filtros de peso, estado y ordenamiento."""
    try:
        estrategia = EstrategiaOrden(_texto("orden", "").upper())
    except ValueError:
        estrategia = None

    pedidos = servicio.listar(
        peso_min=_decimal("peso_min"),
        peso_max=_decimal("peso_max"),
        solo_pendientes=_texto("solo_pendientes", "1") not in ("0", "false", "no", ""),
        orden=estrategia,
        descendente=_texto("descendente", "0") in ("1", "true", "si", "sí"),
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
    )

    if not resultado.ok:
        return _error(resultado.mensaje)

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

    plan = servicio.planear(
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


@app.route("/api/carga/generar", methods=["POST"])
def api_generar():
    """Genera pedidos aleatorios con direcciones."""
    try:
        cantidad = int(float(_texto("cantidad", "50")))
    except ValueError:
        return _error("La cantidad debe ser un numero.")

    semilla = _texto("semilla")

    resultado = servicio.generar_masivo(
        cantidad,
        con_direcciones=_texto("direcciones", "1") not in ("0", "false", "no"),
        semilla=int(semilla) if semilla else None,
    )

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json({
        "generados": len(resultado.datos or []),
        "mensaje": resultado.mensaje,
    })


@app.route("/api/carga/archivo", methods=["POST"])
def api_importar():
    """Importa pedidos desde un archivo CSV, TXT o XLSX subido."""
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

    return _json(serializar(resultado.datos))


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
    """Simula un plan de carga SIN despachar nada."""
    resultado = servicio.planear(
        estrategia=_estrategia_reparto(),
        prioritario=_texto("prioritario") or None,
        objetivo=_objetivo(),
    )

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json(serializar(resultado.datos))


@app.route("/api/salidas/estrategias", methods=["GET"])
def api_estrategias():
    """Compara las tres estrategias de reparto sobre los mismos datos."""
    resultado = servicio.comparar_estrategias(_texto("prioritario") or None)

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json(serializar(resultado.datos))


@app.route("/api/salidas/confirmar", methods=["POST"])
def api_confirmar():
    """Confirma el plan: marca los pedidos como despachados.

    El plan se vuelve a calcular en el SERVIDOR en lugar de confiar en los
    codigos que envia el navegador. Es una decision de seguridad: si se
    aceptara la lista del cliente, alguien podria manipularla a mano y
    despachar pedidos que nunca estuvieron en el plan. El servidor es la
    unica fuente de verdad.
    """
    plan = servicio.planear(
        estrategia=_estrategia_reparto(),
        prioritario=_texto("prioritario") or None,
        objetivo=_objetivo(),
    )

    if not plan.ok:
        return _error(plan.mensaje)

    resultado = servicio.confirmar_salida(plan.datos)

    if not resultado.ok:
        return _error(resultado.mensaje)

    return _json({
        "mensaje": resultado.mensaje,
        "salida": serializar(resultado.datos),
    })


@app.route("/api/salidas/historial", methods=["GET"])
def api_historial():
    """Historial de salidas ya confirmadas."""
    return _json({
        "salidas": [
            {
                "id": salida.id,
                "fecha": salida.fecha,
                "cantidad": salida.cantidad,
                "peso_total": salida.peso_total,
                "capacidad": salida.capacidad,
                "ocupacion": round(salida.peso_total / salida.capacidad * 100, 1) if salida.capacidad else 0.0,
                "estrategia": salida.estrategia,
                "prioritario": salida.prioritario,
                "codigos": salida.codigos,
            }
            for salida in servicio.historial()
        ]
    })


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
