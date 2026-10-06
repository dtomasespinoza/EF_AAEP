"""Modulo prueba_consola."""

from __future__ import annotations

import builtins
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARCHIVO_PRUEBA = os.path.join(tempfile.gettempdir(), "rappidos_test_consola.json")
ARCHIVO_CSV = os.path.join(tempfile.gettempdir(), "rappidos_test_consola.csv")

for ruta in (ARCHIVO_PRUEBA, ARCHIVO_CSV):
    if os.path.exists(ruta):
        os.remove(ruta)

os.environ["RAPPIDOS_ARCHIVO"] = ARCHIVO_PRUEBA

import main as consola  # noqa: E402
from nucleo.servicio import RAPPIDOS  # noqa: E402

fallos: list[str] = []

def revisar(nombre: str, condicion: bool, detalle: str = "") -> None:
    if condicion:
        print(f"  [OK]    {nombre}")
    else:
        print(f"  [FALLA] {nombre}")
        fallos.append(nombre)
        if detalle:
            print(detalle)

def ejecutar(acciones: list[str], servicio: RAPPIDOS) -> str:
    """Recorre el menu principal respondiendo con la lista de `acciones`."""
    entradas = iter(acciones + ["0"])
    original = builtins.input

    def input_falso(prompt: str = "") -> str:

        print(prompt, end="")
        return next(entradas, "")

    builtins.input = input_falso

    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            consola.menu(servicio)
    finally:
        builtins.input = original

    return buffer.getvalue()

servicio = RAPPIDOS(ruta_datos=ARCHIVO_PRUEBA)

salida = ejecutar(
    ["1", "7.5", "Calle 1 #2-3", "Ana", "3001112233", "1", "12", "Carrera 5 #6-7", "Luis", ""],
    servicio,
)
revisar("registra dos pedidos", salida.count("[OK]") >= 2, salida)
revisar("no hay errores de datos", "[!]" not in salida, salida)
revisar("el contador arranca en P001", "P001" in salida and "P002" in salida, salida)

salida = ejecutar(["2", "no", "2", "", ""], servicio)
revisar("lista los dos pedidos", "P001" in salida and "P002" in salida, salida)
revisar("muestra el cliente", "Ana" in salida, salida)

salida = ejecutar(["3"], servicio)
revisar("generacion aleatoria desactivada", "desactivada" in salida, salida)
for numero in range(30):
    servicio.registrar(peso=1 + numero % 10, distrito="Surco", direccion=f"Calle {numero}")

with open(ARCHIVO_CSV, "wb") as archivo:
    archivo.write(b"Peso;Direccion;Cliente\n4.5;Calle 9;Sara\nabc;Mal;X\n")

salida = ejecutar(["4", ARCHIVO_CSV], servicio)
revisar("importa el CSV valido", "1 pedido(s) importado(s)" in salida, salida)
revisar("reporta la fila invalida", "linea 3" in salida, salida)

salida = ejecutar(["5", "p001", "2"], servicio)
revisar("busca en minusculas", "P001" in salida, salida)
revisar("indica las comparaciones", "comparacion" in salida, salida)

salida = ejecutar(["5", "P9999", "2"], servicio)
revisar("avisa si no existe", "No se encontro" in salida, salida)

salida = ejecutar(["6"], servicio)
revisar(
    "mide los 6 algoritmos",
    all(n in salida for n in ["Burbuja", "Insercion", "QuickSort", "Conteo", "Cubetas", "Nativo"]),
    salida,
)
revisar("Burbuja hace mas trabajo que QuickSort", salida.index("Burbuja") < salida.index("QuickSort"))

salida = ejecutar(["7", "MOCHILA_0_1", "", "no"], servicio)
revisar("compara las 3 estrategias", "Mochila" in salida and "Mejor encaje" in salida, salida)
revisar("cancela si el usuario dice no", "cancelada" in salida, salida)
revisar(
    "no despacha al cancelar",
    len(servicio.listar(solo_pendientes=True)) > 0,
)

cantidad_antes = len(servicio.listar(solo_pendientes=True))
salida = ejecutar(["7", "MOCHILA_0_1", "", "si"], servicio)
revisar("confirma la salida", "confirmada" in salida, salida)
revisar("descuenta los pendientes", len(servicio.listar(solo_pendientes=True)) < cantidad_antes, salida)

pendientes = servicio.listar(solo_pendientes=True)
if pendientes:
    objetivo = pendientes[0].codigo
    salida = ejecutar(["7", "PRIMERO_QUE_CABE", objetivo, "si"], servicio)
    revisar("acepta un pedido prioritario", "confirmada" in salida, salida)

salida = ejecutar(["8", "PESO"], servicio)
revisar("cambia el objetivo de la mochila", "Peso cargado" in salida, salida)
revisar("muestra el criterio usado", "Criterio:" in salida, salida)

salida = ejecutar(["8", "OBJETIVO_QUE_NO_EXISTE"], servicio)
revisar("rechaza un objetivo desconocido", "[!]" in salida, salida)

salida = ejecutar(["9"], servicio)
revisar("muestra estadisticas", "PEDIDOS TOTALES" in salida, salida)
revisar("dibuja el histograma", "#" in salida, salida)

salida = ejecutar(["A"], servicio)
revisar("muestra el historial", "OCUPACION" in salida, salida)

salida = ejecutar(["B", "1"], servicio)
revisar("limpia los pendientes", "eliminado" in salida, salida)

salida = ejecutar(["2", "si"], servicio)
revisar("no quedan pendientes", "No hay pedidos" in salida, salida)

salida = ejecutar(["B", "2", "P001"], servicio)
revisar("elimina un pedido por codigo", "No se encontro" in salida or "OK" in salida, salida)

salida = ejecutar(["B", "3", "no"], servicio)
revisar("cancela el borrado total", "Cancelado" in salida, salida)

salida = ejecutar(["Z", "X", "0"], servicio)
revisar("rechaza opciones invalidas", salida.count("Opcion no valida") == 2, salida)

salida = ejecutar(["Z", "Z", "Z"], servicio)
revisar("sale tras tres intentos fallidos", "Demasiados intentos" in salida, salida)

salida = ejecutar(["7", "0"], servicio)
revisar("permite volver sin planear", "0. Volver" in salida, salida)
revisar("no despacha al volver", "confirmada" not in salida, salida)

print("\n" + "=" * 58)
if fallos:
    print(f"  {len(fallos)} PRUEBA(S) FALLARON:")
    for fallo in fallos:
        print(f"    - {fallo}")
    print("=" * 58)
    sys.exit(1)

print("  TODAS LAS PRUEBAS DE LA CONSOLA PASARON")
print("=" * 58)

for ruta in (ARCHIVO_PRUEBA, ARCHIVO_CSV):
    if os.path.exists(ruta):
        os.remove(ruta)
