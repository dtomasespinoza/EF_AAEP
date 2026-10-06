"""Algoritmos de ordenamiento, busqueda y sus mediciones."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, List, Sequence

from .modelos import EstrategiaOrden

MAXIMO_RANGO_CONTEO = 500_000

@dataclass
class Metrica:
    """Resultado de medir un algoritmo sobre una entrada concreta."""

    nombre: str
    elementos: int
    comparaciones: int
    intercambios: int
    milisegundos: float

    @property
    def pasos_por_elemento(self) -> float:
        """Intensidad del algoritmo: pasos / elemento."""
        if self.elementos == 0:
            return 0.0
        return (self.comparaciones + self.intercambios) / self.elementos

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "elementos": self.elementos,
            "comparaciones": self.comparaciones,
            "intercambios": self.intercambios,
            "milisegundos": round(self.milisegundos, 4),
            "pasos_por_elemento": round(self.pasos_por_elemento, 2),
        }

@dataclass
class ResultadoOrden:
    """Lista ya ordenada junto con la metrica de como se produjo."""

    elementos: List[Any]
    metrica: Metrica

class Contador:
    """Contador mutable compartido por los algoritmos."""

    __slots__ = ("comparaciones", "intercambios")

    def __init__(self) -> None:
        self.comparaciones = 0
        self.intercambios = 0

    def comparar(self) -> None:
        self.comparaciones += 1

    def intercambiar(self) -> None:
        self.intercambios += 1

class Cronometro:
    """Mide el tiempo de una seccion de codigo con `perf_counter`."""

    __slots__ = ("_inicio", "milisegundos")

    def __init__(self) -> None:
        self._inicio = 0.0
        self.milisegundos = 0.0

    def __enter__(self) -> "Cronometro":
        self._inicio = time.perf_counter()
        return self

    def __exit__(self, *_args) -> bool:
        self.milisegundos = (time.perf_counter() - self._inicio) * 1000
        return False

def ordenamiento_burbuja(elementos: Sequence[Any], clave: Callable[[Any], Any]) -> ResultadoOrden:
    """Ordenamiento por burbuja con bandera de corte temprano."""
    contador = Contador()

    with Cronometro() as cronometro:
        datos = list(elementos)
        total = len(datos)

        for i in range(total):
            ordenado = True

            for j in range(0, total - i - 1):
                contador.comparar()

                if clave(datos[j]) > clave(datos[j + 1]):
                    datos[j], datos[j + 1] = datos[j + 1], datos[j]
                    contador.intercambiar()
                    ordenado = False

            if ordenado:
                break

    metrica = Metrica(
        nombre="Burbuja",
        elementos=len(datos),
        comparaciones=contador.comparaciones,
        intercambios=contador.intercambios,
        milisegundos=cronometro.milisegundos,
    )
    return ResultadoOrden(datos, metrica)

def ordenamiento_insercion(elementos: Sequence[Any], clave: Callable[[Any], Any]) -> ResultadoOrden:
    """Ordenamiento por insercion."""
    contador = Contador()

    with Cronometro() as cronometro:
        datos = list(elementos)
        total = len(datos)

        for i in range(1, total):
            actual = datos[i]
            j = i - 1

            while j >= 0:
                contador.comparar()

                if clave(datos[j]) > clave(actual):
                    datos[j + 1] = datos[j]
                    contador.intercambiar()
                    j -= 1
                else:
                    break

            datos[j + 1] = actual

    metrica = Metrica(
        nombre="Insercion",
        elementos=len(datos),
        comparaciones=contador.comparaciones,
        intercambios=contador.intercambios,
        milisegundos=cronometro.milisegundos,
    )
    return ResultadoOrden(datos, metrica)

def ordenamiento_quicksort(elementos: Sequence[Any], clave: Callable[[Any], Any]) -> ResultadoOrden:
    """QuickSort con particion de Lomuto."""
    contador = Contador()

    with Cronometro() as cronometro:
        datos = list(elementos)
        _quicksort(datos, 0, len(datos) - 1, clave, contador)

    metrica = Metrica(
        nombre="QuickSort",
        elementos=len(datos),
        comparaciones=contador.comparaciones,
        intercambios=contador.intercambios,
        milisegundos=cronometro.milisegundos,
    )
    return ResultadoOrden(datos, metrica)

def _quicksort(
    datos: List[Any],
    bajo: int,
    alto: int,
    clave: Callable[[Any], Any],
    contador: Contador,
) -> None:
    """Division recursiva de QuickSort."""
    if bajo >= alto:
        return

    pivote_indice = _particionar(datos, bajo, alto, clave, contador)

    _quicksort(datos, bajo, pivote_indice - 1, clave, contador)
    _quicksort(datos, pivote_indice + 1, alto, clave, contador)

def _particionar(
    datos: List[Any],
    bajo: int,
    alto: int,
    clave: Callable[[Any], Any],
    contador: Contador,
) -> int:
    """Reordena in-place y devuelve la posicion final del pivote."""
    pivote = clave(datos[alto])
    i = bajo - 1

    for j in range(bajo, alto):
        contador.comparar()

        if clave(datos[j]) <= pivote:
            i += 1
            datos[i], datos[j] = datos[j], datos[i]
            if i != j:
                contador.intercambiar()

    datos[i + 1], datos[alto] = datos[alto], datos[i + 1]
    if i + 1 != alto:
        contador.intercambiar()

    return i + 1

def _decimales(valor: Any, maximo: int = 6) -> int:
    """Cuantos decimales tiene un numero, hasta un tope."""
    texto = f"{float(valor):.10f}".rstrip("0")

    if "." not in texto:
        return 0

    return min(len(texto.split(".")[1]), maximo)

def ordenamiento_conteo(elementos: Sequence[Any], clave: Callable[[Any], Any]) -> ResultadoOrden:
    """Ordenamiento por conteo."""
    contador = Contador()

    with Cronometro() as cronometro:
        datos = list(elementos)

        if not datos:
            metrica = Metrica("Conteo", 0, 0, 0, cronometro.milisegundos)
            return ResultadoOrden(datos, metrica)

        valores = [clave(elemento) for elemento in datos]
        escala = 10 ** max(_decimales(valor) for valor in valores)
        enteros = [int(round(float(valor) * escala)) for valor in valores]

        menor = min(enteros)
        rango = max(enteros) - menor + 1

        if rango > MAXIMO_RANGO_CONTEO:
            return ordenamiento_cubetas(datos, clave)

        cubetas: List[List[Any]] = [[] for _ in range(rango)]
        for elemento, indice in zip(datos, enteros):
            cubetas[indice - menor].append(elemento)
            contador.comparar()

        ordenados: List[Any] = []
        for cubeta in cubetas:
            contador.comparar()
            ordenados.extend(cubeta)

    metrica = Metrica(
        nombre="Conteo",
        elementos=len(datos),
        comparaciones=contador.comparaciones,
        intercambios=contador.intercambios,
        milisegundos=cronometro.milisegundos,
    )
    return ResultadoOrden(ordenados, metrica)

def ordenamiento_cubetas(elementos: Sequence[Any], clave: Callable[[Any], Any]) -> ResultadoOrden:
    """Ordenamiento por cubetas (bucket sort) con distribucion uniforme."""
    contador = Contador()

    with Cronometro() as cronometro:
        datos = list(elementos)
        total = len(datos)

        if total == 0:
            metrica = Metrica("Cubetas", 0, 0, 0, cronometro.milisegundos)
            return ResultadoOrden(datos, metrica)

        valores = [clave(elemento) for elemento in datos]
        menor = min(valores)
        mayor = max(valores)
        extension = (mayor - menor) or 1
        numero_cubetas = total

        cubetas: List[List[Any]] = [[] for _ in range(numero_cubetas)]
        for elemento in datos:
            posicion = ((clave(elemento) - menor) / extension) * numero_cubetas
            cubetas[min(int(posicion), numero_cubetas - 1)].append(elemento)
            contador.comparar()

        ordenados: List[Any] = []
        for cubeta in cubetas:
            contador.comparar()

            if not cubeta:
                continue

            for i in range(1, len(cubeta)):
                actual = cubeta[i]
                j = i - 1

                while j >= 0:
                    contador.comparar()

                    if clave(cubeta[j]) > clave(actual):
                        cubeta[j + 1] = cubeta[j]
                        contador.intercambiar()
                        j -= 1
                    else:
                        break

                cubeta[j + 1] = actual

            ordenados.extend(cubeta)

    metrica = Metrica(
        nombre="Cubetas",
        elementos=len(datos),
        comparaciones=contador.comparaciones,
        intercambios=contador.intercambios,
        milisegundos=cronometro.milisegundos,
    )
    return ResultadoOrden(ordenados, metrica)

def ordenamiento_nativo(elementos: Sequence[Any], clave: Callable[[Any], Any]) -> ResultadoOrden:
    """Linea base: `sorted()` de Python, que internamente usa TimSort."""
    with Cronometro() as cronometro:
        datos = sorted(elementos, key=clave)

    total = len(datos)
    metrica = Metrica(
        nombre="Nativo (sorted)",
        elementos=total,
        comparaciones=_comparaciones_estimadas_nativas(total),
        intercambios=0,
        milisegundos=cronometro.milisegundos,
    )
    return ResultadoOrden(datos, metrica)

def _comparaciones_estimadas_nativas(total: int) -> int:
    """Estima las comparaciones de un ordenamiento O(n log n) clasico."""
    if total < 2:
        return total

    niveles = total.bit_length() - 1
    return total * max(niveles, 1)

ALGORITMOS = {
    EstrategiaOrden.BURBUJA: ordenamiento_burbuja,
    EstrategiaOrden.INSERCION: ordenamiento_insercion,
    EstrategiaOrden.QUICKSORT: ordenamiento_quicksort,
    EstrategiaOrden.CONTEO: ordenamiento_conteo,
    EstrategiaOrden.CUBETAS: ordenamiento_cubetas,
    EstrategiaOrden.NATIVO: ordenamiento_nativo,
}

def ordenar(
    elementos: Sequence[Any],
    clave: Callable[[Any], Any],
    estrategia: EstrategiaOrden,
    descendente: bool = False,
) -> ResultadoOrden:
    """Punto de entrada unico para ordenar cualquier secuencia."""
    resultado = ALGORITMOS[estrategia](elementos, clave)

    if descendente:
        resultado.elementos.reverse()
        resultado.metrica.nombre = f"{resultado.metrica.nombre} (desc)"

    return resultado

def comparar_algoritmos(
    elementos: Sequence[Any],
    clave: Callable[[Any], Any],
    descendente: bool = False,
) -> List[Metrica]:
    """Ejecuta TODOS los algoritmos sobre la misma entrada y devuelve metricas."""
    metricas: List[Metrica] = []

    for estrategia in EstrategiaOrden:
        resultado = ordenar(elementos, clave, estrategia, descendente)
        metricas.append(resultado.metrica)

    return metricas

@dataclass
class ResultadoBusqueda:
    """Resultado de una busqueda, con su coste real en comparaciones."""

    encontrado: bool
    indice: int = -1
    elemento: Any = None
    comparaciones: int = 0
    algoritmo: str = ""

    def a_dict(self) -> dict:
        return {
            "encontrado": self.encontrado,
            "indice": self.indice,
            "comparaciones": self.comparaciones,
            "algoritmo": self.algoritmo,
        }

def busqueda_lineal(elementos: Sequence[Any], objetivo: Any, clave: Callable[[Any], Any]) -> ResultadoBusqueda:
    """Busqueda lineal o secuencial."""
    contador = Contador()
    total = len(elementos)

    for indice in range(total):
        contador.comparar()

        if clave(elementos[indice]) == objetivo:
            return ResultadoBusqueda(
                True, indice, elementos[indice], contador.comparaciones, "Lineal"
            )

    return ResultadoBusqueda(False, -1, None, contador.comparaciones, "Lineal")

def busqueda_binaria(elementos: Sequence[Any], objetivo: Any, clave: Callable[[Any], Any]) -> ResultadoBusqueda:
    """Busqueda binaria iterativa. PRECONDICION: la lista debe estar ordenada."""
    inicio = 0
    fin = len(elementos) - 1
    comparaciones = 0

    while inicio <= fin:
        mitad = (inicio + fin) // 2
        valor = clave(elementos[mitad])
        comparaciones += 1

        if valor == objetivo:
            return ResultadoBusqueda(
                True, mitad, elementos[mitad], comparaciones, "Binaria"
            )

        if valor < objetivo:
            inicio = mitad + 1
        else:
            fin = mitad - 1

    return ResultadoBusqueda(False, -1, None, comparaciones, "Binaria")

def busqueda_lineal_codigo(pedidos: Sequence[Any], codigo: str) -> ResultadoBusqueda:
    """Busqueda lineal por codigo de pedido. No exige orden previo."""
    comparaciones = 0

    for indice, pedido in enumerate(pedidos):
        comparaciones += 1

        if pedido.codigo == codigo:
            return ResultadoBusqueda(
                True, indice, pedido, comparaciones, "Lineal"
            )

    return ResultadoBusqueda(False, -1, None, comparaciones, "Lineal")

def busqueda_binaria_codigo(pedidos: Sequence[Any], codigo: str) -> ResultadoBusqueda:
    """Busqueda binaria por codigo, sobre la lista ORDENADA por codigo."""
    ordenados = sorted(pedidos, key=lambda pedido: pedido.codigo)
    resultado = busqueda_binaria(ordenados, codigo, lambda pedido: pedido.codigo)
    resultado.algoritmo = "Binaria"
    return resultado
