"""Modulo prueba_api."""

import io
import os
import sys
import tempfile

RAIZ = r"C:\DESARROLLO\PYTHON\ProyectoFinal\ProyectoFinal"
sys.path.insert(0, RAIZ)

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

def post(ruta, json=None, data=None, content_type=None, **kwargs):
    return cliente.post(ruta, json=json if json is not None else None, data=data, content_type=content_type, **kwargs)

seccion_titulo("1. PAGINAS HTML")

for ruta, esperado in [
    ("/", "Panel de control"),
    ("/pedidos", "Pedidos"),
    ("/carga", "Carga masiva"),
    ("/salidas", "Preparar salida"),
    ("/estadisticas", "Estadísticas"),
    ("/analisis", "Comparación y Búsqueda"),
]:
    respuesta = cliente.get(ruta)
    revisar(f"GET {ruta}", respuesta.status_code == 200, f"-> {respuesta.status_code}")
    revisar(
        f"  contenido '{esperado}'",
        esperado in respuesta.get_data(as_text=True),
    )

respuesta = cliente.get("/ruta-inexistente")
revisar("GET /ruta-inexistente", respuesta.status_code == 404, f"-> {respuesta.status_code}")
revisar("  contenido 'No encontramos'", "No encontramos" in respuesta.get_data(as_text=True))

for activo in ("css/estilos.css", "js/app.js"):
    respuesta = cliente.get(f"/static/{activo}")
    revisar(f"GET /static/{activo}", respuesta.status_code == 200, f"-> {respuesta.status_code}")

seccion_titulo("2. ALTA DE PEDIDOS")

respuesta = post("/api/pedidos", {"peso": 5.5, "direccion": "Calle 10 #3-22", "cliente": "Ana"})
datos = respuesta.get_json()
revisar("POST /api/pedidos", datos["exito"] and datos["datos"]["pedido"]["codigo"] == "P001", datos["mensaje"])
revisar("  peso guardado", datos["datos"]["pedido"]["peso"] == 5.5)

respuesta = post("/api/pedidos", {"peso": "2,75"})
revisar("acepta coma decimal", respuesta.get_json()["exito"] and respuesta.get_json()["datos"]["pedido"]["peso"] == 2.75)

for peso, motivo in [
    (0, "peso cero"),
    (-5, "peso negativo"),
    (31, "sobre el maximo"),
    ("abc", "no numerico"),
    ("", "vacio"),
]:
    respuesta = post("/api/pedidos", {"peso": peso})
    revisar(f"rechaza {motivo}", not respuesta.get_json()["exito"], respuesta.get_json()["mensaje"])

seccion_titulo("3. CARGA MASIVA POR ARCHIVO")

respuesta = post(
    "/api/carga/archivo",
    data={
        "archivo": (io.BytesIO(b"Peso,Distrito,Direccion,Cliente,Telefono\n5.0,La Castilla,Calle 1,Ana,3001112222\n7.5,El Cedro,Carrera 4,Luis,3102223333\n"), "pedidos.csv")
    },
    content_type="multipart/form-data",
)
datos = respuesta.get_json()
revisar("sube archivo CSV", datos["exito"], datos["mensaje"])
revisar("devuelve token de confirmacion", "token" in datos["datos"], str(datos["datos"]))
token = datos["datos"].get("token")

respuesta = post("/api/carga/confirmar", {"token": token})
datos = respuesta.get_json()
revisar("confirma importacion", datos["exito"], datos["mensaje"])
revisar("registra 2 pedidos", datos["datos"]["pedidos"] and len(datos["datos"]["pedidos"]) == 2)

respuesta = post("/api/carga/confirmar", {"token": token})
revisar("token no reutilizable", not respuesta.get_json()["exito"], respuesta.get_json()["mensaje"])

seccion_titulo("4. LISTADO Y FILTROS")

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

for algoritmo in ["BURBUJA", "INSERCION", "QUICKSORT", "CONTEO", "CUBETAS", "NATIVO"]:
    resultado = get("/api/pedidos", orden=algoritmo).get_json()["datos"]["pedidos"]
    pesos_alg = [p["peso"] for p in resultado]
    revisar(f"{algoritmo} ordena ascendente", pesos_alg == sorted(pesos_alg), f"{pesos_alg[:4]}")

seccion_titulo("5. BUSQUEDA")

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

seccion_titulo("6. ALGORITMOS DE ORDENAMIENTO")

respuesta = get("/api/algoritmos")
datos = respuesta.get_json()["datos"]
metricas = datos["metricas"]

revisar("mide 6 algoritmos", len(metricas) == 6, f"{len(metricas)}")

nombres = {m["nombre"] for m in metricas}
revisar("incluye burbuja y quicksort", "Burbuja" in nombres and "QuickSort" in nombres, str(nombres))

burbuja = next(m for m in metricas if m["nombre"] == "Burbuja")
quicksort = next(m for m in metricas if m["nombre"] == "QuickSort")
revisar("burbuja hace mas comparaciones que quicksort", burbuja["comparaciones"] >= quicksort["comparaciones"],
        f"{burbuja['comparaciones']} vs {quicksort['comparaciones']}")

detalle = datos.get("detalle")
revisar("incluye el orden resultante", detalle is not None and "pedidos" in detalle)

if detalle:
    pesos_detalle = [p["peso"] for p in detalle["pedidos"]]
    revisar("detalle ordenado ascendente", pesos_detalle == sorted(pesos_detalle), f"{pesos_detalle[:4]}")

seccion_titulo("7. CARGA DESDE ARCHIVOS")

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
revisar("vista previa devuelve token", "token" in datos, str(datos))
token = datos.get("token")

confirmar = cliente.post("/api/carga/confirmar", json={"token": token})
revisar("confirma tras vista previa", confirmar.get_json()["exito"], confirmar.get_json()["mensaje"])

vp = datos["vista_previa"]
revisar("importa CSV valido", vp["total_importados"] == 2, f"{vp['total_importados']}")
revisar("  acepta coma decimal", any(p["peso"] == 8.25 for p in vp["pedidos"]))
revisar("  reporta 3 errores", vp["total_errores"] == 3, f"{vp['total_errores']}")
revisar("  indica el numero de linea", vp["errores"][0]["linea"] == 4, str(vp["errores"][0]))

respuesta = cliente.post(
    "/api/carga/archivo",
    data={"archivo": (io.BytesIO(b"2.5\n7.75\n# comentario\n1.2\n"), "pesos.txt")},
    content_type="multipart/form-data",
)
datos = respuesta.get_json()["datos"]
revisar("vista previa TXT devuelve token", "token" in datos)
vp = datos["vista_previa"]
revisar("importa TXT", vp["total_importados"] == 3, f"{vp['total_importados']}")
revisar("  ignora comentarios", vp["total_importados"] == 3)

respuesta = cliente.post(
    "/api/carga/archivo",
    data={"archivo": (io.BytesIO(b"4.5,Calle 9 #1-2,Luis\n12,Carrera 7 #3-4,Sara\n"), "sin.csv")},
    content_type="multipart/form-data",
)
datos = respuesta.get_json()["datos"]
vp = datos["vista_previa"]
revisar("CSV sin encabezado", vp["total_importados"] == 2, f"{vp['total_importados']}")

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
    vp = datos.get("vista_previa", datos)
    revisar("importa XLSX", vp["total_importados"] == 2, f"{vp['total_importados']}")
except ImportError:
    print("  [omitido] openpyxl no instalado")

respuesta = cliente.post(
    "/api/carga/archivo",
    data={"archivo": (io.BytesIO(b"contenido"), "documento.pdf")},
    content_type="multipart/form-data",
)
revisar("rechaza formato no soportado", not respuesta.get_json()["exito"])

revisar("rechaza peticion sin archivo", not cliente.post("/api/carga/archivo").get_json()["exito"])

respuesta = cliente.get("/api/carga/plantilla")
revisar("plantilla CSV descargable", respuesta.status_code == 200 and b"Peso" in respuesta.data)

seccion_titulo("8. PLAN DE SALIDA")

pendientes_antes = get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"]

respuesta = post("/api/salidas/plan", {"estrategia": "MOCHILA_0_1", "objetivo": "CANTIDAD"})
datos = respuesta.get_json()["datos"]
revisar("planifica mochila 0/1", respuesta.get_json()["exito"], respuesta.get_json()["mensaje"])
plan_datos = datos
revisar("  no supera la capacidad", plan_datos["peso_total"] <= plan_datos["capacidad"] * len(plan_datos.get("viajes", [1])) + 0.001, f"{plan_datos['peso_total']} > {plan_datos['capacidad']*len(plan_datos.get('viajes',[1]))}")
revisar("  nunca vacio", plan_datos["total_pedidos"] > 0)

revisar("  simular no despacha", get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"] == pendientes_antes)

heuristica = post("/api/salidas/plan", {"estrategia": "PRIMERO_QUE_CABE"}).get_json()["datos"]
revisar("mochila 0/1 gana en pedidos", plan_datos["total_pedidos"] >= heuristica["total_pedidos"],
        f"mochila={plan_datos['total_pedidos']} heuristica={heuristica['total_pedidos']}")

best_fit = post("/api/salidas/plan", {"estrategia": "MEJOR_ENCAGE"}).get_json()["datos"]
revisar("mejor encaje cabe en capacidad", best_fit["peso_total"] <= best_fit["capacidad"] * len(best_fit.get("viajes", [1])) + 0.001)

por_peso = post("/api/salidas/plan", {"estrategia": "MOCHILA_0_1", "objetivo": "PESO"}).get_json()["datos"]
revisar("objetivo peso carga mas kg", por_peso["peso_total"] >= plan_datos["peso_total"] - 0.001,
        f"peso={por_peso['peso_total']} cantidad={datos['peso_total']}")

disponibles = get("/api/pedidos", solo_pendientes=1, peso_max=8).get_json()["datos"]["pedidos"]
if disponibles:
    codigo = disponibles[0]["codigo"]
    plan = post("/api/salidas/plan", {"estrategia": "MOCHILA_0_1", "prioritario": codigo}).get_json()["datos"]
    seleccionado = plan["viajes"][0]["pedidos"] if plan["viajes"] else []
    incluido = any(p["codigo"] == codigo for p in seleccionado)
    revisar("prioritario siempre se incluye", incluido, codigo)
    revisar("  respeta la capacidad", plan["peso_total"] <= plan["capacidad"] * len(plan.get("viajes", [1])) + 0.001)

respuesta = post("/api/salidas/plan", {"prioritario": "P9999"})
revisar("prioritario inexistente da error", not respuesta.get_json()["exito"])

comparacion = get("/api/salidas/estrategias").get_json()["datos"]
revisar("compara 3 estrategias", len(comparacion["planes"]) == 3, f"{len(comparacion['planes'])}")
revisar("  indica la mejor", comparacion["mejor"] in [p["estrategia"] for p in comparacion["planes"]])

seccion_titulo("9. CONFIRMAR SALIDA")

plan = post("/api/salidas/plan", {"estrategia": "MOCHILA_0_1"}).get_json()["datos"]
codigos = [p["codigo"] for viaje in plan["viajes"] for p in viaje["pedidos"]]

respuesta = post("/api/salidas/confirmar", {"estrategia": "MOCHILA_0_1"})
datos = respuesta.get_json()["datos"]
revisar("confirma salida", respuesta.get_json()["exito"], respuesta.get_json()["mensaje"])
revisar("  marca los mismos codigos", datos["salida"]["codigos"] == codigos)
revisar("  descuenta los pendientes",
        get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"] == pendientes_antes - plan["total_pedidos"])

todos = get("/api/pedidos", solo_pendientes=0).get_json()["datos"]["pedidos"]
despachados = [p for p in todos if p["codigo"] in codigos]
revisar("los despachados se conservan", len(despachados) == len(codigos))
revisar("  quedan marcados DESPACHADO", all(p["estado"] == "DESPACHADO" for p in despachados))
revisar("  tienen fecha de despacho", all(p["fecha_despacho"] for p in despachados))

revisar("reabre un pedido", post(f"/api/pedidos/{codigos[0]}/reabrir").get_json()["exito"])
revisar("  vuelve a PENDIENTE",
        get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"] == pendientes_antes - plan["total_pedidos"] + 1)
revisar("  no se puede reabrir dos veces",
        not post(f"/api/pedidos/{codigos[0]}/reabrir").get_json()["exito"])

historial = get("/api/salidas/historial").get_json()["datos"]["salidas"]
revisar("historial registra la salida", len(historial) >= 1)
revisar("  con peso y ocupacion", all("ocupacion" in s for s in historial))

seccion_titulo("10. ELIMINAR Y LIMPIAR")

revisar("elimina existente", cliente.delete(f"/api/pedidos/{codigos[0]}").get_json()["exito"])
revisar("  eliminar dos veces da 404", cliente.delete(f"/api/pedidos/{codigos[0]}").status_code == 404)

revisar("limpiar pendientes", post("/api/limpiar", {"tipo": "pendientes"}).get_json()["exito"])
revisar("  queda todo despachado", get("/api/pedidos", solo_pendientes=1).get_json()["datos"]["total"] == 0)

revisar("rechaza plan sin pedidos", not post("/api/salidas/plan").get_json()["exito"])

respuesta = post("/api/limpiar", {"tipo": "todo"})
revisar("limpia todo", respuesta.get_json()["exito"])
revisar("  queda vacio", get("/api/pedidos", solo_pendientes=0).get_json()["datos"]["total"] == 0)
revisar("  reinicia el contador", post("/api/pedidos", {"peso": 1}).get_json()["datos"]["pedido"]["codigo"] == "P001")

seccion_titulo("11. ESTADISTICAS Y CATALOGO")

post("/api/limpiar", {"tipo": "pendientes"})

for numero in range(25):
    post("/api/pedidos", {"peso": 1 + numero % 10, "distrito": "La Castilla", "direccion": f"Calle {numero}"})
datos = get("/api/estadisticas").get_json()["datos"]
revisar("devuelve resumen", "resumen" in datos)
revisar("  con 25 pendientes", datos["resumen"]["pendientes"] == 25, str(datos["resumen"]["pendientes"]))
revisar("  viajes >= 1", datos["resumen"]["viajes_necesarios"] >= 1)
revisar("  ocupacion <= 100", datos["resumen"]["ocupacion_teorica"] <= 100, str(datos["resumen"]["ocupacion_teorica"]))
revisar("devuelve histograma", len(datos["histograma"]) > 0)
revisar("  suma = pendientes", sum(b["cantidad"] for b in datos["histograma"]) == 25)
revisar("devuelve zonas", isinstance(datos.get("distribucion_distritos") or datos.get("distribucion_zonas"), list))
revisar("devuelve info del almacen", "ruta" in datos["almacen"])

catalogo = get("/api/catalogo").get_json()["datos"]
revisar("catalogo con 3 estrategias", len(catalogo["estrategias_reparto"]) == 3)
revisar("  cada una con descripcion", all("descripcion" in e for e in catalogo["estrategias_reparto"]))
revisar("  6 algoritmos de orden", len(catalogo["algoritmos_orden"]) == 6)
revisar("  2 objetivos", len(catalogo["objetivos"]) == 2)

codigo = get("/api/pedidos", campo="CODIGO").get_json()["datos"]["pedidos"][0]["codigo"]
r = cliente.put(f"/api/pedidos/{codigo}", json={"direccion": "Nueva direccion", "telefono": "", "distrito": "Centro"})
revisar("edita pedido individual y permite vaciar campos", r.get_json()["exito"] and r.get_json()["datos"]["pedido"]["telefono"] == "")
codigos_editar = [p["codigo"] for p in get("/api/pedidos", campo="CODIGO").get_json()["datos"]["pedidos"][:2]]
r = post("/api/pedidos/editar-masivo", {"codigos": codigos_editar, "distrito": "Sur", "peso": 2})
revisar("edicion masiva", r.get_json()["exito"] and all(p["distrito"] == "Sur" and p["peso"] == 2 for p in r.get_json()["datos"]["pedidos"]))
revisar("filtra distrito", get("/api/pedidos", distrito="Sur").get_json()["datos"]["total"] == 2)
plan = post("/api/salidas/plan", {"viajes": 0}).get_json()["datos"]
revisar("prepara varias mochilas", len(plan["viajes"]) > 1 and all(v["peso_total"] <= v["capacidad"] for v in plan["viajes"]))
salida = post("/api/salidas/confirmar", {"viajes": 0}).get_json()["datos"]["salida"]
detalle = get(f"/api/salidas/{salida['id']}").get_json()["datos"]
revisar("detalle conserva todos los pedidos y viajes", len(detalle["detalle"]) == plan["total_pedidos"] and detalle["viajes"] == len(plan["viajes"]))
original = detalle["detalle"][0]["direccion"]
cliente.put(f"/api/pedidos/{detalle['detalle'][0]['codigo']}", json={"direccion": "Modificado despues"})
revisar("historial conserva direccion al despachar", get(f"/api/salidas/{salida['id']}").get_json()["datos"]["detalle"][0]["direccion"] == original)

seccion_titulo("12. MANEJO DE ERRORES")

revisar("API inexistente da JSON 404",
        get("/api/no-existe").status_code == 404 and get("/api/no-existe").is_json)

revisar("priorizar inexistente da 404", post("/api/pedidos/P9999/priorizar").status_code == 404)

revisar("el sobre de respuesta es uniforme",
        all(set(get(ruta, **params).get_json()) == {"exito", "mensaje", "datos"}
            for ruta, params in [("/api/pedidos", {}), ("/api/estadisticas", {}), ("/api/catalogo", {})]))

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
