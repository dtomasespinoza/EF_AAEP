"""
 nucleo.algoritmos
 =================

 Implementaciones clasicas de ordenamiento y busqueda, escritas a mano y
 "instrumentadas": ademas de devolver el resultado, cada algoritmo reporta
 cuantas comparaciones e intercambios realizo y cuanto tardo.

 Para que la medicion sea valida, todos los algoritmos se invocan sobre una
 COPIA de la misma lista de entrada: si no, el segundo algoritmo recibiria la
 lista ya ordenada y mediria un caso trivial (mejor caso) en vez del caso
 promedio.

 Complejidades Big-O (n = cantidad de pedidos):

    Burbuja      O(n^2) tiempo / O(1) memoria extra
    Insercion    O(n^2) tiempo / O(1) memoria extra
    QuickSort    O(n log n) promedio, O(n^2) peor caso / O(log n) pila
    Conteo       O(n + k) tiempo, k = rango de valores / O(n + k) memoria
    Cubetas      O(n + k) promedio / O(n + k) memoria
    Nativo       O(n log n) (TimSort)

 Este modulo es NUCLEO PURO: no imprime nada y no depende de la interfaz.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, List, Sequence

from .modelos import EstrategiaOrden


# Tope de posiciones que el ordenamiento por conteo esta dispuesto a reservar.
# El dominio de RAPPIDOS (pesos de hasta 30 kg con dos decimales) necesita solo
# unas 3000, asi que este limite nunca se alcanza en la practica: es una red de
# seguridad para datos inesperados.
MAXIMO_RANGO_CONTEO = 500_000


# --------------------------------------------------------------------------
# Metrica de ejecucion
# --------------------------------------------------------------------------


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
        """Intensidad del algoritmo: pasos / elemento.

        Normalizar respecto a n es lo que revela el crecimiento asintotico:
        en un O(n^2) esta razon crece de forma lineal con n, mientras que en
        un O(n log n) se mantiene casi plana.
        """
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
    """Contador mutable compartido por los algoritmos.

    Se pasa por referencia a las funciones auxiliares para poder contar
    comparaciones reales sin inflar la firma de cada una. Al ser un objeto
    mutable, las funciones recursivas pueden actualizarlo sin `nonlocal`.
    """

    __slots__ = ("comparaciones", "intercambios")

    def __init__(self) -> None:
        self.comparaciones = 0
        self.intercambios = 0

    def comparar(self) -> None:
        self.comparaciones += 1

    def intercambiar(self) -> None:
        self.intercambios += 1


class Cronometro:
    """Mide el tiempo de una seccion de codigo con `perf_counter`.

    Se usa un objeto context manager para no repetir el par
    inicio/fin en cada algoritmo. `perf_counter` es el reloj de mayor
    resolucion de la biblioteca estandar y es monotono, a diferencia de
    `time.time`.
    """

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


# --------------------------------------------------------------------------
# Algoritmos de ordenamiento
# --------------------------------------------------------------------------


def ordenamiento_burbuja(elementos: Sequence[Any], clave: Callable[[Any], Any]) -> ResultadoOrden:
    """Ordenamiento por burbuja con bandera de corte temprano.

    Variante clasica: recorre la lista comparando vecinos e intercambiandolos
    si estan desordenados, arrastrando asi el valor mayor hacia el final en
    cada pasada.

    La bandera `ordenado` es la unica optimizacion frente a la version
    ingenua: si una pasada completa no produce ningun intercambio, la lista
    ya esta ordenada y se rompe el ciclo. En el mejor caso (lista ya
    ordenada) el algoritmo baja de O(n^2) a O(n), que es el caso mas
    frecuente en RAPPIDOS porque los pedidos llegan casi ordenados por peso.

    Parametros
    ----------
    elementos : secuencia de datos a ordenar. No se modifica.
    clave : funcion que extrae el valor de comparacion, por ejemplo
            `lambda p: p.peso`.

    Retorna
    -------
    ResultadoOrden con la lista ordenada (copia) y su metrica de ejecucion.
    """
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
    """Ordenamiento por insercion.

    Construye la lista ordenada de izquierda a derecha: en cada posicion i
    toma el elemento y lo desplaza hacia la izquierda hasta encontrar su
    lugar. Es el algoritmo natural cuando los datos llegan casi ordenados, y
    es la etapa de umbral de TimSort.

    A diferencia de QuickSort, es estable: dos elementos con la misma clave
    conservan su orden relativo.
    """
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
    """QuickSort con particion de Lomuto.

    Elige un pivote (el ultimo elemento) y reparte la lista en dos: los
    menores a la izquierda, los mayores o iguales a la derecha. Luego repite
    el proceso sobre cada mitad (divide y venceras).

    Tomar el ultimo elemento como pivote y trabajar sobre sublistas es la
    version didactica mas simple; su contraprestacion es que una lista ya
    ORDENADA degrada a O(n^2). El caso promedio de esta aplicacion (pesos
    aleatorios) no sufre esa degradacion.

    La recursion ocupa O(log n) en promedio, porque la particion deja las
    dos mitades balanceadas.
    """
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
    """Cuantos decimales tiene un numero, hasta un tope.

    El conteo por conteo necesita convertir cada valor en un indice entero.
    Si los pesos vienen en kilos con dos decimales, el indice es el peso
    multiplicado por 100; pero hay que SABER cuantos decimales usar, y eso
    no se puede suponer.

    Se formatea con precision fija y se cuentan los decimales, en vez de
    usar `str(0.1 + 0.2)`, que daria 16 decimales por el error de coma
    flotante y reservaria una memoria desmedida. El tope de 6 decimales
    evita que un dato raro construya un arreglo gigantesco.
    """
    texto = f"{float(valor):.10f}".rstrip("0")

    if "." not in texto:
        return 0

    return min(len(texto.split(".")[1]), maximo)


def ordenamiento_conteo(elementos: Sequence[Any], clave: Callable[[Any], Any]) -> ResultadoOrden:
    """Ordenamiento por conteo.

    Aprovcha que los pesos de un pedido viven en un rango acotado: de 0 a 30
    kg, es decir de 0 a 3000 centesimas de kilogramo. Cuenta cuantas veces
    aparece cada peso y luego reconstruye la lista recorriendo el rango.

    Es el unico algoritmo presente con complejidad O(n + k) GARANTIZADA (no
    solo promedio), a cambio de consumir O(k) memoria extra, donde k es el
    rango de valores.

    En el dominio de RAPPIDOS es el algoritmo adecuado, porque el peso ya se
    maneja como entero en centesimas: no hay error de redondeo al usarlo
    como indice de un arreglo.

    Detalle de implementacion: los indices se calculan sobre el peso
    MULTIPLICADO POR 10^decimales, no con `int(peso)`. Si se truncara cada
    peso directamente, 8.21 kg y 8.71 kg cairian en la MISMA posicion y el
    orden final seria incorrecto: es el error clasico de aplicar conteo
    sobre datos con decimales sin escalar antes.

    Si el rango resultara desmedido, se delega en cubetas, que tambien es
    O(n + k) promedio pero no reserva memoria para todo el rango.
    """
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
    """Ordenamiento por cubetas (bucket sort) con distribucion uniforme.

    Reparte los elementos en `n` cubetas segun su posicion relativa dentro
    del rango [min, max], ordena cada cubeta con insercion y concatena.

    Es O(n + k) en promedio y degrada a O(n^2) cuando todos los valores caen
    en una misma cubeta. La diferencia con el ordenamiento por conteo esta
    en el tamano del arreglo auxiliar: aqui es n (cantidad de elementos),
    mientras que en conteo es k (rango de valores). Por eso conteo es
    preferible en RAPPIDOS, donde el rango es de solo 3000 valores.
    """
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
    """Linea base: `sorted()` de Python, que internamente usa TimSort.

    No se implementa a mano, pero se mide con el mismo criterio que los
    demas. TimSort combina insercion para bloques pequenos con merge para
    bloques grandes, y por eso es mas rapido que QuickSort puro en el caso
    promedio. Notar que su numero de comparaciones es una ESTIMACION
    analitica (n * log2 n), porque el codigo interno de CPython es nativo y
    no expone un contador.
    """
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
    """Estima las comparaciones de un ordenamiento O(n log n) clasico.

    Se usa `int(n * log2(n))`, que se obtiene al equilibrar los niveles del
    arbol de decision. Solo aplica a TimSort, cuyo contador interno no es
    accesible desde Python.
    """
    if total < 2:
        return total

    niveles = total.bit_length() - 1
    return total * max(niveles, 1)


#: Tabla de despacho: la interfaz elige por nombre, nunca por un numero.
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
    """Punto de entrada unico para ordenar cualquier secuencia.

    Centraliza la eleccion del algoritmo y el sentido de orden, de modo que
    ninguna otra capa del sistema tenga que conocer la firma de cada
    implementacion.
    """
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
    """Ejecuta TODOS los algoritmos sobre la misma entrada y devuelve metricas.

    Cada algoritmo recibe `list(elementos)`, es decir una copia propia. Si se
    compartiera la misma lista, el primero en ejecutarse la dejaria ordenada
    y los demas medirian el mejor caso en lugar del caso promedio: la
    comparacion seria invalida.
    """
    metricas: List[Metrica] = []

    for estrategia in EstrategiaOrden:
        resultado = ordenar(elementos, clave, estrategia, descendente)
        metricas.append(resultado.metrica)

    return metricas


# --------------------------------------------------------------------------
# Algoritmos de busqueda
# --------------------------------------------------------------------------


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
    """Busqueda lineal o secuencial.

    Recorre la lista comparando cada elemento con el objetivo, uno por uno y
    de principio a fin. No exige ningun orden previo, pero su peor caso es
    O(n): puede terminar revisando los n elementos.

    Se conserva porque es la unica opcion valida cuando la lista no esta
    ordenada, y sirve de referencia para medir la ventaja asintotica de la
    busqueda binaria.
    """
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
    """Busqueda binaria iterativa. PRECONDICION: la lista debe estar ordenada.

    En cada paso compara el objetivo con el elemento del medio y descarta
    la mitad donde el objetivo no puede encontrarse: si el objetivo es
    mayor, busca en la mitad derecha; si es menor, en la izquierda.

    Complejidad O(log n): en lugar de revisar n elementos hace cerca de
    log2(n) comparaciones. Con 1 000 pedidos revisa unas 10, y con un
    millon unas 20. Esa diferencia asintotica es la que la vuelve superior
    a la lineal cuando se repite la busqueda muchas veces.

    El intervalo se mantiene cerrado [inicio, fin], y `mitad = (inicio +
    fin) // 2` evita el desbordamiento de numero entero que produciria
    `(inicio + fin) / 2` en otros lenguajes.
    """
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
    """Busqueda binaria por codigo, sobre la lista ORDENADA por codigo.

    Los codigos tienen el formato P001, P002, ... con relleno de ceros a la
    izquierda, de modo que el orden alfabetico coincide con el orden
    numerico y la busqueda binaria es aplicable.

    Si se quitara el relleno (P1, P2, P10) el orden alfabetico dejaria de
    coincidir con el numerico, la precondicion se violaria y la busqueda
    binaria devolveria resultados incorrectos. Esa es la razon del formato
    `P%03d` y no es un detalle cosmetico.
    """
    ordenados = sorted(pedidos, key=lambda pedido: pedido.codigo)
    resultado = busqueda_binaria(ordenados, codigo, lambda pedido: pedido.codigo)
    resultado.algoritmo = "Binaria"
    return resultado
