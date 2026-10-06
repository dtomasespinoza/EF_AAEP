"""Interfaz de consola."""

from __future__ import annotations

import os
import sys
from typing import Optional

from nucleo import (
    CAPACIDAD_VEHICULO_KG,
    PESO_MAXIMO_KG,
    PESO_MINIMO_KG,
    RAPPIDOS,
    EstrategiaOrden,
    EstrategiaReparto,
    ObjetivoMochila,
)

LINEA = "=" * 60
SEP = "-" * 60

def titulo(texto: str) -> None:
    print(f"\n{LINEA}\n  {texto}\n{LINEA}")

def exito(mensaje: str) -> None:
    print(f"  [OK]   {mensaje}")

def fallo(mensaje: str) -> None:
    print(f"  [!]    {mensaje}")

def aviso(mensaje: str) -> None:
    print(f"  [i]    {mensaje}")

def limpiar_pantalla() -> None:
    os.system("cls" if os.name == "nt" else "clear")

def pedir(etiqueta: str, por_defecto: str = "") -> str:
    """Lee una linea de texto, ofreciendo un valor por defecto."""
    sufijo = f" [{por_defecto}]" if por_defecto else ""
    return input(f"  {etiqueta}{sufijo}: ").strip() or por_defecto

def pedir_opcion(texto: str, opciones: dict) -> Optional[str]:
    """Muestra un menu y devuelve la clave elegida, o None si se cancela."""
    print(f"  {texto}")
    for clave, etiqueta in opciones.items():
        print(f"    {clave}. {etiqueta}")
    print("    0. Volver")

    while True:
        eleccion = input("  Opcion: ").strip().upper()
        if eleccion in ("0", ""):
            return None
        if eleccion in opciones:
            return eleccion
        fallo("Opcion no valida.")

def confirmar(texto: str) -> bool:
    return pedir(f"{texto} (si/no)", "no").lower().startswith("s")

def formatear_peso(valor) -> str:
    try:
        return f"{float(valor):.2f} kg"
    except (TypeError, ValueError):
        return "0.00 kg"

def accion_registrar(servicio: RAPPIDOS) -> None:
    titulo("REGISTRAR PEDIDO")

    print(f"  Peso permitido: {PESO_MINIMO_KG} - {PESO_MAXIMO_KG} kg")
    print(f"  Capacidad del vehiculo: {CAPACIDAD_VEHICULO_KG} kg\n")

    peso = pedir("Peso del pedido (kg)")
    direccion = pedir("Direccion")
    cliente = pedir("Cliente")
    telefono = pedir("Telefono")

    resultado = servicio.registrar(peso, direccion, cliente, telefono)

    if resultado.ok:
        exito(f"Pedido {resultado.datos.codigo} registrado: {resultado.mensaje}")
    else:
        fallo(resultado.mensaje)

def accion_listar(servicio: RAPPIDOS) -> None:
    titulo("LISTAR PEDIDOS")

    pendientes = pedir("Solo pendientes? (si/no)", "si").lower().startswith("s")

    print("\n  Ordenar por:")
    print("    1. Codigo")
    print("    2. Peso de menor a mayor")
    print("    3. Peso de mayor a menor")
    eleccion = pedir("Opcion", "2")

    descendente = eleccion == "3"

    peso_min = pedir("Peso minimo (vacio = sin filtro)")
    peso_max = pedir("Peso maximo (vacio = sin filtro)")

    pedidos = servicio.listar(
        peso_min=float(peso_min) if peso_min else None,
        peso_max=float(peso_max) if peso_max else None,
        solo_pendientes=pendientes,
        descendente=descendente,
    )

    if not pedidos:
        aviso("No hay pedidos para mostrar.")
        return

    print(f"\n{SEP}")
    print(f"  {'CODIGO':<10} {'PESO':>10}  {'CLIENTE':<18} DIRECCION")
    print(SEP)

    for pedido in pedidos:
        marca = "*" if pedido.prioridad else " "
        print(
            f" {marca}{pedido.codigo:<9} {formatear_peso(pedido.peso):>10}  "
            f"{pedido.cliente[:18]:<18} {pedido.direccion[:32]}"
        )

    print(SEP)
    aviso(f"(*) prioritario    Total: {len(pedidos)} pedido(s)")

def accion_generar(servicio: RAPPIDOS) -> None:
    titulo("GENERAR PEDIDOS ALEATORIOS")

    aviso("Esta opcion ha sido desactivada: el sistema ahora importa por archivo con confirmacion.")
    aviso("Para generar datos de prueba, descarga la plantilla y sube un archivo, o registra manualmente.")
    return

def accion_importar(servicio: RAPPIDOS) -> None:
    titulo("IMPORTAR DESDE ARCHIVO")

    aviso("Formatos: CSV (con o sin encabezado), TXT o XLSX.")
    ruta = pedir("Ruta del archivo")

    try:
        with open(ruta, "rb") as archivo:
            contenido = archivo.read()
    except OSError as error:
        fallo(f"No se pudo leer el archivo: {error}")
        return

    resultado = servicio.importar(os.path.basename(ruta), contenido)

    if not resultado.ok:
        fallo(resultado.mensaje)
        return

    datos = resultado.datos

    for error in datos.errores:
        print(f"    linea {error.linea}: {error.mensaje}")

    exito(resultado.mensaje)

def accion_buscar(servicio: RAPPIDOS) -> None:
    titulo("BUSCAR PEDIDO")

    codigo = pedir("Codigo (p001, P001...)")
    algoritmo = pedir("Algoritmo (1=lineal, 2=binaria)", "2")

    resultado = servicio.buscar(codigo, usar_binaria=algoritmo != "1")

    if not resultado.ok:
        fallo(resultado.mensaje)
        return

    pedido = resultado.datos["pedido"]
    busqueda = resultado.datos["busqueda"]

    print()
    print(f"  {SEP}")
    print(f"  Codigo    : {pedido.codigo}")
    print(f"  Peso      : {formatear_peso(pedido.peso)}")
    print(f"  Direccion : {pedido.direccion or '(sin direccion)'}")
    print(f"  Cliente   : {pedido.cliente or '(sin cliente)'}")
    print(f"  Estado    : {pedido.estado.value}")
    print(SEP)
    exito(
        f"Busqueda {'binaria' if algoritmo != '1' else 'lineal'}: "
        f"{busqueda['comparaciones']} comparacion(es) en el indice {busqueda['indice']}."
    )

def accion_medir_algoritmos(servicio: RAPPIDOS) -> None:
    titulo("COMPARAR ALGORITMOS DE ORDENAMIENTO")

    pendientes = len(servicio.listar(solo_pendientes=True))
    aviso(f"Vamos a ordenar los {pendientes} pedido(s) pendiente(s) de 6 formas.")

    resultado = servicio.comparar_algoritmos()

    if not resultado.ok:
        fallo(resultado.mensaje)
        return

    print(f"\n  {'ALGORITMO':<14} {'COMPARACIONES':>15} {'INTERCAMBIOS':>14} {'TIEMPO':>10}")
    print(SEP)

    for metrica in resultado.datos["metricas"]:
        print(
            f"  {metrica['nombre']:<14} {metrica['comparaciones']:>15,} "
            f"{metrica['intercambios']:>14,} {metrica['milisegundos']:>8.3f} ms"
        )

    print(SEP)
    aviso("Todos receives la MISMA lista sin ordenar: por eso la comparacion vale.")

def accion_planear(servicio: RAPPIDOS) -> None:
    titulo("PREPARAR SALIDA")

    opcion = pedir_opcion(
        "Como quieres cargar el vehiculo?",
        {estrategia.name: estrategia.etiqueta for estrategia in EstrategiaReparto},
    )

    if opcion is None:
        return

    estrategia = EstrategiaReparto[opcion]
    prioritario = pedir("Codigo prioritario (vacio = ninguno)") or None

    resultado = servicio.planear(estrategia=estrategia, prioritario=prioritario)

    if not resultado.ok:
        fallo(resultado.mensaje)
        return

    comparacion = servicio.comparar_estrategias(prioritario)

    if comparacion.ok:
        print("\n  Las tres estrategias sobre los mismos pedidos:")
        print(f"  {'ESTRATEGIA':<22} {'PEDIDOS':>9} {'PESO':>10} {'LIBRE':>10}")
        print(SEP)

        for plan in comparacion.datos["planes"]:
            marca = " <" if plan["estrategia"] == comparacion.datos["mejor"] else ""
            print(
                f"  {plan['estrategia_etiqueta']:<22} {plan['cantidad']:>9} "
                f"{formatear_peso(plan['peso_total']):>10} "
                f"{formatear_peso(plan['disponible']):>10}{marca}"
            )

        print(SEP)
        aviso(f"Optimo: {comparacion.mensaje}")

    if not confirmar("\nConfirmar esta salida?"):
        aviso("Salida cancelada. No se modifico nada.")
        return

    resultado = servicio.confirmar_salida(resultado.datos)

    if resultado.ok:
        exito(resultado.mensaje)
    else:
        fallo(resultado.mensaje)

def accion_objetivo(servicio: RAPPIDOS) -> None:
    titulo("MOCHILA 0/1: OBJETIVO DE LA COMBINACION")

    for clave, etiqueta in ObjetivoMochila.ETIQUETAS.items():
        print(f"    {clave}: {etiqueta}")

    objetivo = pedir("Objetivo", ObjetivoMochila.CANTIDAD).upper()

    if objetivo not in ObjetivoMochila.ETIQUETAS:
        fallo(f"'{objetivo}' no es un objetivo valido.")
        return

    resultado = servicio.planear(
        estrategia=EstrategiaReparto.MOCHILA_0_1, objetivo=objetivo
    )

    if not resultado.ok:
        fallo(resultado.mensaje)
        return

    plan = resultado.datos
    exito(resultado.mensaje)
    aviso(f"Peso cargado: {formatear_peso(plan.peso_total)} de {plan.capacidad} kg.")
    aviso(f"Criterio: {plan.objetivo}")

def accion_estadisticas(servicio: RAPPIDOS) -> None:
    titulo("ESTADISTICAS")

    resultado = servicio.estadisticas()

    if not resultado.ok:
        fallo(resultado.mensaje)
        return

    resumen = resultado.datos["resumen"]

    print(f"\n  {'PEDIDOS TOTALES':<24} {resumen['total_pedidos']}")
    print(f"  {'Pendientes':<24} {resumen['pendientes']}")
    print(f"  {'Despachados':<24} {resumen['despachados']}")
    print(f"  {'Peso pendiente':<24} {formatear_peso(resumen['peso_pendientes'])}")
    print(f"  {'Peso promedio':<24} {formatear_peso(resumen['peso_promedio'])}")
    print(f"  {'Rango':<24} {formatear_peso(resumen['peso_minimo'])} - "
          f"{formatear_peso(resumen['peso_maximo'])}")
    print(f"  {'Viajes minimos':<24} {resumen['viajes_necesarios']}")
    print(f"  {'Ocupacion teorica':<24} {resumen['ocupacion_teorica']}%")

    print(f"\n  {'DISTRIBUCION POR PESO':<24}")
    print(SEP)

    barras = resultado.datos["histograma"]
    mayor = max((barra["cantidad"] for barra in barras), default=0) or 1

    for barra in barras:
        filled = "#" * round(barra["cantidad"] / mayor * 28)
        print(f"  {barra['rango']:<18} {barra['cantidad']:>4}  {filled}")

    zonas = resultado.datos.get("distribucion_zonas") or []
    if zonas:
        print(f"\n  {'ZONAS MAS PEDIDAS':<24}")
        print(SEP)
        for zona in zonas[:5]:
            print(f"  {zona['zona']:<24} {zona['cantidad']:>4} pedido(s)")

def accion_historial(servicio: RAPPIDOS) -> None:
    titulo("HISTORIAL DE SALIDAS")

    salidas = servicio.historial()

    if not salidas:
        aviso("Todavia no se ha confirmado ninguna salida.")
        return

    print(f"\n  {'FECHA':<22} {'PEDIDOS':>8} {'PESO':>10} {'OCUPACION':>10}")
    print(SEP)

    for salida in salidas:
        ocupacion = (
            salida.peso_total / salida.capacidad * 100 if salida.capacidad else 0
        )
        print(
            f"  {salida.fecha[:19]:<22} {salida.cantidad:>8} "
            f"{formatear_peso(salida.peso_total):>10} {ocupacion:>9.1f}%"
        )

    print(SEP)

def accion_limpiar(servicio: RAPPIDOS) -> None:
    titulo("ELIMINAR PEDIDOS")

    opcion = pedir_opcion(
        "Que quieres borrar?",
        {
            "1": "Solo los pendientes",
            "2": "Un pedido por codigo",
            "3": "Todo el sistema (incluye el historial)",
        },
    )

    if opcion is None:
        return

    if opcion == "1":
        resultado = servicio.limpiar(solo_pendientes=True)
    elif opcion == "2":
        resultado = servicio.eliminar(pedir("Codigo").upper())
    else:
        if not confirmar("Esto borra TODOS los datos. Continuar?"):
            aviso("Cancelado.")
            return
        resultado = servicio.limpiar(solo_pendientes=False)

    if resultado.ok:
        exito(resultado.mensaje)
    else:
        fallo(resultado.mensaje)

MENU = {
    "1": ("Registrar pedido", accion_registrar),
    "2": ("Listar pedidos", accion_listar),
    "3": ("Generar pedidos aleatorios", accion_generar),
    "4": ("Importar desde archivo", accion_importar),
    "5": ("Buscar pedido", accion_buscar),
    "6": ("Comparar algoritmos de ordenamiento", accion_medir_algoritmos),
    "7": ("Preparar salida", accion_planear),
    "8": ("Mochila 0/1: cambiar objetivo", accion_objetivo),
    "9": ("Estadisticas", accion_estadisticas),
    "A": ("Historial de salidas", accion_historial),
    "B": ("Eliminar pedidos", accion_limpiar),
}

def menu(servicio: RAPPIDOS) -> None:

    intentos_fallidos = 0
    maximo_intentos = 3

    while intentos_fallidos < maximo_intentos:
        print("\n" + LINEA)
        print("  RAPPIDOS - SISTEMA DE PEDIDOS (consola)")
        print(LINEA)

        for clave, (etiqueta, _) in MENU.items():
            print(f"    {clave}. {etiqueta}")
        print("    0. Salir")

        pendientes = len(servicio.listar(solo_pendientes=True))
        print(SEP)
        print(f"  Pedidos pendientes: {pendientes}")
        print("  (La version web se arranca con: python app.py)")

        opcion = input("\n  Ingrese una opcion: ").strip().upper()

        if opcion == "0":
            print("\n  Saliendo del programa...")
            return

        if opcion in MENU:
            intentos_fallidos = 0
            _, accion = MENU[opcion]
            try:
                accion(servicio)
            except KeyboardInterrupt:
                print("\n  Operacion cancelada.")
            except (ValueError, TypeError) as error:
                fallo(f"Dato invalido: {error}")
            except OSError as error:
                fallo(f"Error de archivo: {error}")
        else:
            intentos_fallidos += 1
            restantes = maximo_intentos - intentos_fallidos
            fallo(
                "Opcion no valida."
                if restantes
                else f"Opcion no valida. Le quedan {restantes} intento(s); se sale."
            )

    print("\n  Demasiados intentos fallidos. Saliendo del programa...")

def principal() -> int:
    servicio = RAPPIDOS()

    print(LINEA)
    print("  RAPPIDOS - SISTEMA DE PEDIDOS")
    print("  Consola sobre el mismo nucleo que usa la version web")
    print(LINEA)

    menu(servicio)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(principal())
    except KeyboardInterrupt:
        print("\n  Saliendo del programa...")
        sys.exit(0)
