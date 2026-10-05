"""
Prueba de extremo a extremo de la API web de RAPPIDOS.

Levanta la aplicacion con el cliente de pruebas de Flask, que simula las
peticiones HTTP sin abrir un puerto, y recorre todos los casos de uso: alta
de pedidos, carga masiva, busquedas, algoritmos, plan de salida, confirmacion
y borrado. Cada seccion imprime OK o el error encontrado.
"""

import io
import os
import sys
import tempfile

RAIZ = r"C:\DESARROLLO\PYTHON\ProyectoFinal\ProyectoFinal"
sys.path.insert(0, RAIZ)

# Se cambia el archivo de datos ANTES de importar app, para que las pruebas
# no toquen los pedidos reales del desarrollador.
ARCHIVO_PRUEBA = os.path.join(tempfile.gettempdir(), "rappidos_test_api.json")
if os.path.exists(ARCHIVO_PRUEBA):
    os.remove(ARCHIVO_PRUEBA)

os.environ["RAPPIDOS_ARCHIVO"] = ARCHIVO_PRUEBA

import app as modulo_app  # noqa: E402

modulo_app.servicio = modulo_app.RAPPIDOS(ruta_datos=ARCHIVO_PRUEBA)

cliente = modulo_app.app.test_client()

fallos = []
seccion = ""


def revisar(nombre, condicion, detalle=""):
    if condicion:
        print(f"  [OK]   {nombre}")
    else:
        print(f"  [FALLA] {nombre} {detalle}")
        fallos.append(nombre)


def seccion_titulo(titulo):
    global seccion
    seccion = titulo
    print(f"\n{titulo}")


def get(ruta, **params):
    return cliente.get(ruta, query_string=params)


def post(ruta, json=None):
    return cliente.post(ruta, json=json if json is not None else {})


# ==========================================================================
seccion_titulo("1. PAGINAS HTML")
# ==========================================================================

for ruta, esperado in [
    ("/", "Panel de control"),
    ("/pedidos", "Pedidos"),
    ("/carga", "Carga masiva"),
    ("/salidas", "Preparar salida"),
    ("/estadisticas", "Estadísticas"),
]:
    respuesta = cliente.get(ruta)
    revisar(f"GET {ruta}", respuesta.status_code == 200, f"-> {respuesta.status_code}")
    revisar(
        f"  contenido '{esperado}'",
        esperado in respuesta.get_data(as_text=True),
    )

# La ruta inexistente debe responder 404 CON la pagina de error, no 500.
respuesta = cliente.get("/ruta-inexistente")
revisar("GET /ruta-inexistente", respuesta.status_code == 404, f"-> {respuesta.status_code}")
revisar("  contenido 'No encontramos'", "No encontramos" in respuesta.get_data(as_text=True))

# El CSS y el JS deben servirse sin error.
for activo in ("css/estilos.css", "js/app.js"):
    respuesta = cliente.get(f"/static/{activo}")
    revisar(f"GET /static/{activo}", respuesta.status_code == 200, f"-> {respuesta.status_code}")

# ==========================================================================
seccion_titulo("2. ALTA DE PEDIDOS")
# ==========================================================================

respuesta = post("/api/pedidos", {"peso": 5.5, "direccion": "Calle 10 #3-22", "cliente": "Ana"})
datos = respuesta.get_json()
revisar("POST /api/pedidos", datos["exito"] and datos["datos"]["pedido"]["codigo"] == "P001", datos["mensaje"])
revisar("  peso guardado", datos["datos"]["pedido"]["peso"] == 5.5)

# Acepta coma decimal, como lo escribe el usuario en un teclado español.
respuesta = post("/api/pedidos", {"peso": "2,75"})
revisar("acepta coma decimal", respuesta.get_json()["exito"] and respuesta.get_json()["datos"]["pedido"]["peso"] == 2.75)

# Validaciones del dominio.
for peso, motivo in [
    (0, "peso cero"),
    (-5, "peso negativo"),
    (31, "sobre el maximo"),
    ("abc", "no numerico"),
    ("", "vacio"),
]:
    respuesta = post("/api/pedidos", {"peso": peso})
    revisar(f"rechaza {motivo}", not respuesta.get_json()["exito"], respuesta.get_json()["mensaje"])

# ==========================================================================
seccion_titulo("3. GENERACION MASIVA")
# ==========================================================================

respuesta = post("/api/carga/generar", {"cantidad": 60, "direcciones": "1", "semilla": "99"})
datos = respuesta.get_json()
revisar("genera 60 pedidos", datos["exito"] and datos["datos"]["generados"] == 60, datos["mensaje"])

# Con la misma semilla debe repetir exactamente los mismos datos. Se comparan
# dos EJECUCIONES INDEPENDIENTES de la misma cantidad: comparar la lista
# acumulada de la base de datos no serviria, porque cada llamada agrega pedidos
# distintos a los ya existentes.
from nucleo.servicio import RAPPIDOS as _Servicio  # noqa: E402


def _generar_en_aislado(cantidad, semilla):
    ruta = os.path.join(tempfile.gettempdir(), f"rappidos_semilla_{semilla}.json")
    if os.path.exists(ruta):
        os.remove(ruta)
    servicio_aislado = _Servicio(ruta_datos=ruta)
    servicio_aislado.generar_masivo(cantidad, con_direcciones=True, semilla=semilla)
    pedidos = servicio_aislado.listar()
    os.remove(ruta)
    return [(p.peso, p.direccion) for p in pedidos]


revisar("semilla reproducible", _generar_en_aislado(8, 99) == _generar_en_aislado(8, 99))
revisar("semillas distintas difieren", _generar_en_aislado(8, 99) != _generar_en_aislado(8, 7))

revisar("rechaza cantidad 0", not post("/api/carga/generar", {"cantidad": 0}).get_json()["exito"])
revisar("rechaza 99999", not post("/api/carga/generar", {"cantidad": 99999}).get_json()["exito"])

# ==========================================================================
seccion_titulo("4. LISTADO Y FILTROS")
# ==========================================================================

todos = get("/api/pedidos", solo_pendientes=1).get_json()["datos"]
revisar("lista pedidos", todos["total"] > 0, f"total={todos['total']}")

pesos = [p["peso"] for p in todos["pedidos"]]
revisar("sin filtro devuelve todos", len(pesos) == todos["total"])

ascendente = get("/api/pedidos", orden="BURBUJA", descendente=0).get_json()["datos"]["pedidos"]
revisar("orden ascendente correcto", all(ascendente[i]["peso"] <= ascendente[i + 1]["peso"] for i in range(len(ascendente) - 1)))

descendente = get("/api/pedidos", orden="BURBUJA", descendente=1).get_json()["datos"]["pedidos"]
revisar("orden descendente correcto", all(descendente[i]["peso"] >= descendente[i + 1]["peso"] for i in range(len(descendente) - 1)))

filtrados = get("/api/pedidos", peso_min=5, peso_max=10).get_json()["datos"]["pedidos"]
revisar("filtro por rango de peso", all(5 <= p["peso"] <= 10 for p in filtrados), f"{len(filtrados)} resultados")

# Cada algoritmo debe producir el MISMO conjunto ordenado.
for algoritmo in ["BURBUJA", "INSERCION", "QUICKSORT", "CONTEO", "CUBETAS", "NATIVO"]:
    resultado = get("/api/pedidos", orden=algoritmo).get_json()["datos"]["pedidos"]
    pesos_alg = [p["peso"] for p in resultado]
    revisar(f"{algoritmo} ordena ascendente", pesos_alg == sorted(pesos_alg), f"{pesos_alg[:4]}")

# ==========================================================================
seccion_titulo("5. BUSQUEDA")
# ==========================================================================

primero = get("/api/pedidos").get_json()["datos"]["pedidos"][0]["codigo"]

respuesta = post("/api/buscar", {"codigo": primero, "algoritmo": "BINARIA"})
revisar("busqueda binaria encuentra", respuesta.get_json()["exito"], respuesta.get_json()["mensaje"])

respuesta = post("/api/buscar", {"codigo": primero.lower(), "algoritmo": "BINARIA"})
revisar("acepta codigo en minuscula", respuesta.get_json()["exito"])

respuesta = post("/api/buscar", {"codigo": "P9999"})
revisar("codigo inexistente da 404", respuesta.status_code == 404)

respuesta = post("/api/buscar", {"codigo": ""})
revisar("codigo vacio da error", not respuesta.get_json()["exito"])

comparacion = post("/api/buscar/comparar", {"codigo": primero}).get_json()["datos"]
revisar("comparacion trae ambos algoritmos", "lineal" in comparacion and "binaria" in comparacion)
revisar("binaria no usa mas comparaciones", comparacion["binaria"]["comparaciones"] <= comparacion["lineal"]["comparaciones"] + 20)

# ==========================================================================
seccion_titulo("6. ALGORITMOS DE ORDENAMIENTO")
# ==========================================================================

respuesta = get("/api/algoritmos")
datos = respuesta.get_json()["datos"]
metricas = datos["metricas"]

revisar("mide 6 algoritmos", len(metricas) == 6, f"{len(metricas)}")

nombres = {m["nombre"] for m in metricas}
revisar("incluye burbuja y quicksort", "Burbuja" in nombres and "QuickSort" in nombres, str(nombres))

burbuja = next(m for m in metricas if m["nombre"] == "Burbuja")
quicksort = next(m for m in metricas if m["nombre"] == "QuickSort")
revisar("burbuja hace mas comparaciones que quicksort", burbuja["comparaciones"] > quicksort["comparaciones"],
        f"{burbuja['comparaciones']} vs {quicksort['comparaciones']}")

detalle = datos.get("detalle")
revisar("incluye el orden resultante", detalle is not None and "pedidos" in detalle)

if detalle:
    pesos_detalle = [p["peso"] for p in detalle["pedidos"]]
    revisar("detalle ordenado ascendente", pesos_detalle == sorted(pesos_detalle), f"{pesos_detalle[:4]}")

# ==========================================================================
seccion_titulo("7. CARGA DESDE ARCHIVOS")
# ==========================================================================

# CSV con punto y coma, con un peso con coma decimal.
csv = (
    "Peso;Direccion;Cliente;Telefono\n"
    "3.5;Calle 1 #2-3;Camila;3001112233\n"
    "8,25;Avenida 5 #6-7;Mateo;3102223344\n"
    "abc;direccion mala;Error;\n"
    "40;sobrepeso;Sobrepeso;\n"
    "0;;PesoCero;\n"
)
respuesta = cliente.post(
    "/api/carga/archivo",
    data={"archivo": (io.BytesIO(csv.encode("utf-8")), "pedidos.csv")},
    content_type="multipart/form-data",
)
datos = respuesta.get_json()["datos"]
revisar("importa CSV valido", datos["total_importados"] == 2, f"{datos['total_importados']}")
revisar("  acepta coma decimal", any(p["peso"] == 8.25 for p in datos["pedidos"]))
revisar("  reporta 3 errores", datos["total_errores"] == 3, f"{datos['total_errores']}")
revisar("  indica el numero de linea", datos["errores"][0]["linea"] == 4, str(datos["errores"][0]))

# TXT con solo pesos.
respuesta = cliente.post(
    "/api/carga/archivo",
    data={"archivo": (io.BytesIO(b"2.5\n7.75\n# comentario\n1.2\n"), "pesos.txt")},
    content_type="multipart/form-data",
)
datos = respuesta.get_json()["datos"]
revisar("importa TXT", datos["total_importados"] == 3, f"{datos['total_importados']}")
revisar("  ignora comentarios", datos["total_importados"] == 3)

# CSV sin encabezado.
respuesta = cliente.post(
    "/api/carga/archivo",
    data={"archivo": (io.BytesIO(b"4.5,Calle 9 #1-2,Luis\n12,Carrera 7 #3-4,Sara\n"), "sin.csv")},
    content_type="multipart/form-data",
)
datos = respuesta.get_json()["datos"]
revisar("CSV sin encabezado", datos["total_importados"] == 2, f"{datos['total_importados']}")

# XLSX.
try:
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.append(["Peso", "Direccion", "Cliente"])
    hoja.append([4.5, "Calle 9 #1-2", "Luis"])
    hoja.append([12.0, "Carrera 7 #3-4", "Sara"])
    buffer = io.BytesIO()
    libro.save(buffer)

    respuesta = cliente.post(
        "/api/carga/archivo",
        data={"archivo": (io.BytesIO(buffer.getvalue()), "libro.xlsx")},
        content_type="multipart/form-data",
    )
    datos = respuesta.get_json()["datos"]
    revisar("importa XLSX", datos["total_importados"] == 2, f"{datos['total_importados']}")
except ImportError:
    print("  [omitido] openpyxl no instalado")

# Formato no soportado.
respuesta = cliente.post(
    "/api/carga/archivo",
    data={"archivo": (io.BytesIO(b"contenido"), "documento.pdf")},
    content_type="multipart/form-data",
)
revisar("rechaza formato no soportado", not respuesta.get_json()["exito"])

# Sin archivo.
revisar("rechaza peticion sin archivo", not cliente.post("/api/carga/archivo").get_json()["exito"])

# Plantilla descargable.
respuesta = cliente.get("/api/carga/plantilla")
revisar("plantilla CSV descargable", respuesta.status_code == 200 and b"Peso" in respuesta.data)

# ==========================================================================
seccion_titulo("8. PLAN DE SALIDA")
# ==========================================================================

pendientes_antes = get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"]

respuesta = post("/api/salidas/plan", {"estrategia": "MOCHILA_0_1", "objetivo": "CANTIDAD"})
datos = respuesta.get_json()["datos"]
revisar("planifica mochila 0/1", respuesta.get_json()["exito"], respuesta.get_json()["mensaje"])
revisar("  no supera la capacidad", datos["peso_total"] <= datos["capacidad"] + 0.001, f"{datos['peso_total']} > {datos['capacidad']}")
revisar("  nunca vacio", datos["cantidad"] > 0)

# Simular NO debe modificar nada.
revisar("  simular no despacha", get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"] == pendientes_antes)

# La mochila 0/1 no puede hacer peor que las heuristicas.
heuristica = post("/api/salidas/plan", {"estrategia": "PRIMERO_QUE_CABE"}).get_json()["datos"]
revisar("mochila 0/1 gana en pedidos", datos["cantidad"] >= heuristica["cantidad"],
        f"mochila={datos['cantidad']} heuristica={heuristica['cantidad']}")

best_fit = post("/api/salidas/plan", {"estrategia": "MEJOR_ENCAGE"}).get_json()["datos"]
revisar("mejor encaje cabe en capacidad", best_fit["peso_total"] <= 30.001)

# Objetivo por peso.
por_peso = post("/api/salidas/plan", {"estrategia": "MOCHILA_0_1", "objetivo": "PESO"}).get_json()["datos"]
revisar("objetivo peso carga mas kg", por_peso["peso_total"] >= datos["peso_total"] - 0.001,
        f"peso={por_peso['peso_total']} cantidad={datos['peso_total']}")

# Pedido prioritario.
disponibles = get("/api/pedidos", solo_pendientes=1, peso_max=8).get_json()["datos"]["pedidos"]
if disponibles:
    codigo = disponibles[0]["codigo"]
    plan = post("/api/salidas/plan", {"estrategia": "MOCHILA_0_1", "prioritario": codigo}).get_json()["datos"]
    incluido = any(p["codigo"] == codigo for p in plan["seleccionados"])
    revisar("prioritario siempre se incluye", incluido, codigo)
    revisar("  respeta la capacidad", plan["peso_total"] <= 30.001)

respuesta = post("/api/salidas/plan", {"prioritario": "P9999"})
revisar("prioritario inexistente da error", not respuesta.get_json()["exito"])

# Comparar estrategias.
comparacion = get("/api/salidas/estrategias").get_json()["datos"]
revisar("compara 3 estrategias", len(comparacion["planes"]) == 3, f"{len(comparacion['planes'])}")
revisar("  indica la mejor", comparacion["mejor"] in [p["estrategia"] for p in comparacion["planes"]])

# ==========================================================================
seccion_titulo("9. CONFIRMAR SALIDA")
# ==========================================================================

plan = post("/api/salidas/plan", {"estrategia": "MOCHILA_0_1"}).get_json()["datos"]
codigos = [p["codigo"] for p in plan["seleccionados"]]

respuesta = post("/api/salidas/confirmar", {"estrategia": "MOCHILA_0_1"})
datos = respuesta.get_json()["datos"]
revisar("confirma salida", respuesta.get_json()["exito"], respuesta.get_json()["mensaje"])
revisar("  marca los mismos codigos", datos["salida"]["codigos"] == codigos)
revisar("  descuenta los pendientes",
        get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"] == pendientes_antes - plan["cantidad"])

# Los despachados siguen existiendo, ahora con otro estado.
todos = get("/api/pedidos", solo_pendientes=0).get_json()["datos"]["pedidos"]
despachados = [p for p in todos if p["codigo"] in codigos]
revisar("los despachados se conservan", len(despachados) == len(codigos))
revisar("  quedan marcados DESPACHADO", all(p["estado"] == "DESPACHADO" for p in despachados))
revisar("  tienen fecha de despacho", all(p["fecha_despacho"] for p in despachados))

# Reabrir uno.
revisar("reabre un pedido", post(f"/api/pedidos/{codigos[0]}/reabrir").get_json()["exito"])
revisar("  vuelve a PENDIENTE",
        get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"] == pendientes_antes - plan["cantidad"] + 1)
revisar("  no se puede reabrir dos veces",
        not post(f"/api/pedidos/{codigos[0]}/reabrir").get_json()["exito"])

# Historial.
historial = get("/api/salidas/historial").get_json()["datos"]["salidas"]
revisar("historial registra la salida", len(historial) >= 1)
revisar("  con peso y ocupacion", all("ocupacion" in s for s in historial))

# ==========================================================================
seccion_titulo("10. ELIMINAR Y LIMPIAR")
# ==========================================================================

revisar("elimina existente", cliente.delete(f"/api/pedidos/{codigos[0]}").get_json()["exito"])
revisar("  eliminar dos veces da 404", cliente.delete(f"/api/pedidos/{codigos[0]}").status_code == 404)

revisar("limpiar pendientes", post("/api/limpiar", {"tipo": "pendientes"}).get_json()["exito"])
revisar("  queda todo despachado", get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"] == 0)

revisar("rechaza plan sin pedidos", not post("/api/salidas/plan").get_json()["exito"])

respuesta = post("/api/limpiar", {"tipo": "todo"})
revisar("limpia todo", respuesta.get_json()["exito"])
revisar("  queda vacio", get("/api/pedidos", solo_pendientes=0).get_json()["datos"]["total"] == 0)
revisar("  reinicia el contador", post("/api/pedidos", {"peso": 1}).get_json()["datos"]["pedido"]["codigo"] == "P001")

# ==========================================================================
seccion_titulo("11. ESTADISTICAS Y CATALOGO")
# ==========================================================================

# La seccion anterior dejo un pedido de prueba (el que creo el contador), asi
# que se borra para partir de cero y poder comparar con numeros exactos.
post("/api/limpiar", {"tipo": "pendientes"})

post("/api/carga/generar", {"cantidad": 25, "semilla": "5"})
datos = get("/api/estadisticas").get_json()["datos"]
revisar("devuelve resumen", "resumen" in datos)
revisar("  con 25 pendientes", datos["resumen"]["pendientes"] == 25, str(datos["resumen"]["pendientes"]))
revisar("  viajes >= 1", datos["resumen"]["viajes_necesarios"] >= 1)
revisar("  ocupacion <= 100", datos["resumen"]["ocupacion_teorica"] <= 100, str(datos["resumen"]["ocupacion_teorica"]))
revisar("devuelve histograma", len(datos["histograma"]) > 0)
revisar("  suma = pendientes", sum(b["cantidad"] for b in datos["histograma"]) == 25)
revisar("devuelve zonas", isinstance(datos["distribucion_zonas"], list))
revisar("devuelve info del almacen", "ruta" in datos["almacen"])

catalogo = get("/api/catalogo").get_json()["datos"]
revisar("catalogo con 3 estrategias", len(catalogo["estrategias_reparto"]) == 3)
revisar("  cada una con descripcion", all("descripcion" in e for e in catalogo["estrategias_reparto"]))
revisar("  6 algoritmos de orden", len(catalogo["algoritmos_orden"]) == 6)
revisar("  2 objetivos", len(catalogo["objetivos"]) == 2)

# ==========================================================================
seccion_titulo("12. MANEJO DE ERRORES")
# ==========================================================================

revisar("API inexistente da JSON 404",
        get("/api/no-existe").status_code == 404 and get("/api/no-existe").is_json)

revisar("priorizar inexistente da 404", post("/api/pedidos/P9999/priorizar").status_code == 404)

revisar("el sobre de respuesta es uniforme",
        all(set(get(ruta, **params).get_json()) == {"exito", "mensaje", "datos"}
            for ruta, params in [("/api/pedidos", {}), ("/api/estadisticas", {}), ("/api/catalogo", {})]))

# ==========================================================================
print("\n" + "=" * 58)
if fallos:
    print(f"  {len(fallos)} PRUEBA(S) FALLARON:")
    for fallo in fallos:
        print(f"    - {fallo}")
    print("=" * 58)
    sys.exit(1)

print("  TODAS LAS PRUEBAS PASARON")
print("=" * 58)

if os.path.exists(ARCHIVO_PRUEBA):
    os.remove(ARCHIVO_PRUEBA)
