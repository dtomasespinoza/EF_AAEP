"""
 nucleo.reparto
 =============

 Seleccion de que pedidos caben en el vehiculo de 30 kg.

 Este modulo reemplaza la logica original de `preparar_salida`, que ordenaba
 los pedidos de MENOR a MAYOR y tomaba el primero que cabia. Esa heuristica
 es correcta pero ineficiente: al tomar primero los pedidos pequenos deja
 huecos que ningun pedido grande puede aprovechar, y al final sobra peso
 que no se puede aprovechar. Aqui se implementan tres estrategias, de la
 mas simple a la optima, para poder COMPARARLAS sobre los mismos datos.

     1. Primero que cabe (First-Fit Decreasing)  heuristica, O(n log n)
     2. Mejor encaje     (Best-Fit Decreasing)    heuristica, O(n^2)
     3. Mochila 0/1       (programacion dinamica)  optimo,   O(n * C)

 NUCLEO PURO: no imprime nada y no conoce la interfaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .algoritmos import Cronometro, ordenar
from .modelos import CAPACIDAD_VEHICULO_KG, EstrategiaOrden, EstrategiaReparto, Pedido

#: Tope de pedidos para la tabla de programacion dinamica. La tabla ocupa
#: O(n * C) celdas; con la capacidad en centesimas (C = 3000) y n = 800 son
#: 2.4 millones de celdas, que es lo que la maquina sostiene con holgura.
#: Por encima de este limite el servicio cae a "Mejor encaje" y lo reporta.
MAX_PEDIDOS_MOCHILA = 800

#: Pesos convertidos a centesimas: el peso es float, pero la tabla de la
#: mochila necesita indices enteros. Se escala por 100 porque 30 kg * 100
#: caben en un int de 16 bits, lo que mantiene la tabla compacta.
ESCALA = 100


class ObjetivoMochila:
    """Criterio a maximizar en la mochila 0/1."""

    CANTIDAD = "CANTIDAD"  # maximizar el numero de pedidos entregados
    PESO = "PESO"  # maximizar los kg transportados

    ETIQUETAS = {
        CANTIDAD: "Maximo numero de pedidos",
        PESO: "Maximo peso transportado",
    }


# --------------------------------------------------------------------------
# Resultado
# --------------------------------------------------------------------------


@dataclass
class Descartado:
    """Pedido que no se llevo, con el motivo."""

    pedido: Pedido
    motivo: str

    def a_dict(self) -> Dict[str, Any]:
        return {
            "codigo": self.pedido.codigo,
            "peso": self.pedido.peso,
            "direccion": self.pedido.direccion,
            "cliente": self.pedido.cliente,
            "motivo": self.motivo,
        }


@dataclass
class PlanSalida:
    """Plan de carga propuesto. Todavia NO modifica el sistema.

    Separar la SIMULACION del plan de su CONFIRMACION es una decision de
    diseno importante: la interfaz puede mostrar el resultado y pedir
    confirmacion sin que quede ningun efecto colateral si el usuario
    cancela. En la version original de consola, cancelar ya habia hecho
    Confirmar el plan ya habia hecho todos los calculos, pero todavia no
    habia borrado nada; aqui el contrato queda explicito en el tipo de dato.
    """

    estrategia: EstrategiaReparto
    capacidad: float
    peso_total: float = 0.0
    seleccionados: List[Pedido] = field(default_factory=list)
    descartados: List[Descartado] = field(default_factory=list)
    prioritario: Optional[str] = None
    milisegundos: float = 0.0
    objetivo: str = ""

    @property
    def cantidad(self) -> int:
        return len(self.seleccionados)

    @property
    def disponible(self) -> float:
        return round(self.capacidad - self.peso_total, 3)

    @property
    def ocupacion(self) -> float:
        """Porcentaje de ocupacion de la capacidad del vehiculo."""
        if self.capacidad <= 0:
            return 0.0
        return round(self.peso_total / self.capacidad * 100, 2)

    def a_dict(self) -> Dict[str, Any]:
        return {
            "estrategia": self.estrategia.value,
            "estrategia_etiqueta": self.estrategia.etiqueta,
            "capacidad": self.capacidad,
            "peso_total": round(self.peso_total, 2),
            "disponible": self.disponible,
            "ocupacion": self.ocupacion,
            "cantidad": self.cantidad,
            "prioritario": self.prioritario,
            "objetivo": self.objetivo,
            "milisegundos": round(self.milisegundos, 3),
            "seleccionados": [p.a_dict() for p in self.seleccionados],
            "descartados": [d.a_dict() for d in self.descartados],
        }


# --------------------------------------------------------------------------
# Punto de entrada
# --------------------------------------------------------------------------


def planear_salida(
    pedidos: Sequence[Pedido],
    estrategia: EstrategiaReparto = EstrategiaReparto.PRIMERO_QUE_CABE,
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
    objetivo: str = ObjetivoMochila.CANTIDAD,
) -> PlanSalida:
    """Genera un plan de carga con la estrategia indicada.

    Parametros
    ----------
    pedidos       : pedidos PENDIENTES a considerar.
    estrategia    : cual de los tres algoritmos aplicar.
    capacidad     : carga maxima del vehiculo, en kg.
    prioritario   : codigo del pedido que debe cargarse SIEMPRE primero.
                    Se reserva su peso antes de repartir el resto.
    objetivo      : solo para la mochila 0/1. Maximizar pedidos o peso.
    """
    if estrategia is EstrategiaReparto.MOCHILA_0_1:
        return mochila_0_1(pedidos, capacidad, prioritario, objetivo)

    if estrategia is EstrategiaReparto.MEJOR_ENCAGE:
        return mejor_encaje(pedidos, capacidad, prioritario)

    return primero_que_cabe(pedidos, capacidad, prioritario)


def comparar_estrategias(
    pedidos: Sequence[Pedido],
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
    objetivo: str = ObjetivoMochila.CANTIDAD,
) -> List[PlanSalida]:
    """Corre las tres estrategias sobre los mismos pedidos.

    Permite demostrar en la interfaz, con datos reales, que la mochila 0/1
    nunca hace peor que las heuristicas y cuanto kg desperdicia cada una.
    """
    planes = []

    for estrategia in EstrategiaReparto:
        planes.append(
            planear_salida(pedidos, estrategia, capacidad, prioritario, objetivo)
        )

    return planes


# --------------------------------------------------------------------------
# 1. Primero que cabe (First-Fit Decreasing)
# --------------------------------------------------------------------------


def primero_que_cabe(
    pedidos: Sequence[Pedido],
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
) -> PlanSalida:
    """First-Fit Decreasing.

    Ordena los pedidos de MAYOR a MENOR peso y los va tomando mientras quepan
    en el espacio restante.

    Mejora directa sobre la version original, que los ordenaba de menor a
    mayor: cargar primero los pesados aprovecha mucho mejor la caja, porque
    los pedidos pequenos rellenan los huecos que dejan los grandes.

    Complejidad: el ordenamiento es O(n log n) con QuickSort y el barrido
    final es O(n), es decir O(n log n) en total.
    """
    with Cronometro() as cronometro:
        prioritario_pedido, resto, capacidad_util = _separar_prioritario(
            pedidos, capacidad, prioritario
        )

        ordenados = ordenar(
            resto, lambda pedido: pedido.peso, EstrategiaOrden.QUICKSORT,
            descendente=True,
        ).elementos

        seleccionados: List[Pedido] = []
        descartados: List[Descartado] = []

        # `capacidad_util` ya descuenta el prioritario, asi que el peso se
        # acumula solo con los pedidos del resto. El prioritario se suma al
        # final para el total de la salida.
        peso_resto = 0.0

        if prioritario_pedido is not None:
            seleccionados.append(prioritario_pedido)

        for pedido in ordenados:
            if peso_resto + pedido.peso <= capacidad_util:
                seleccionados.append(pedido)
                peso_resto += pedido.peso
            else:
                descartados.append(
                    Descartado(
                        pedido,
                        f"no cabe: quedarian {round(capacidad_util - peso_resto, 2)} kg libres",
                    )
                )

        peso_actual = peso_resto + (
            prioritario_pedido.peso if prioritario_pedido is not None else 0.0
        )

    return PlanSalida(
        estrategia=EstrategiaReparto.PRIMERO_QUE_CABE,
        capacidad=capacidad,
        peso_total=peso_actual,
        seleccionados=seleccionados,
        descartados=descartados,
        prioritario=prioritario,
        milisegundos=cronometro.milisegundos,
    )


# --------------------------------------------------------------------------
# 2. Mejor encaje (Best-Fit Decreasing)
# --------------------------------------------------------------------------


def mejor_encaje(
    pedidos: Sequence[Pedido],
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
) -> PlanSalida:
    """Best-Fit Decreasing.

    Igual que First-Fit, pero en lugar de tomar el PRIMER pedido que cabe,
    elige el que deja el menor espacio libre sobrante. Un pedido de 9.5 kg
    tiene prioridad sobre uno de 9 kg si ambos caben, porque el segundo deja
    un hueco inutilizable.

    Complejidad: O(n^2) en el peor caso, porque en cada paso se busca el
    mejor candidato entre los que caben. Es mas costosa que First-Fit, pero
    cabe en el rango de los pedidos reales de una tienda.
    """
    with Cronometro() as cronometro:
        prioritario_pedido, resto, capacidad_util = _separar_prioritario(
            pedidos, capacidad, prioritario
        )

        ordenados = ordenar(
            resto, lambda pedido: pedido.peso, EstrategiaOrden.QUICKSORT,
            descendente=True,
        ).elementos

        seleccionados: List[Pedido] = []
        descartados: List[Descartado] = []

        # Igual que en First-Fit: el prioritario ya esta descontado de
        # `capacidad_util`, asi que no se vuelve a sumar al acumulado.
        peso_resto = 0.0

        if prioritario_pedido is not None:
            seleccionados.append(prioritario_pedido)

        disponibles = list(ordenados)

        while disponibles:
            elegido_indice = -1
            mejor_restante = float("inf")

            for indice, pedido in enumerate(disponibles):
                if peso_resto + pedido.peso > capacidad_util:
                    continue

                restante = capacidad_util - peso_resto - pedido.peso
                if restante < mejor_restante:
                    mejor_restante = restante
                    elegido_indice = indice

            if elegido_indice == -1:
                break

            elegido = disponibles.pop(elegido_indice)
            seleccionados.append(elegido)
            peso_resto += elegido.peso

        for pedido in disponibles:
            descartados.append(
                Descartado(
                    pedido,
                    f"no cabe: quedarian {round(capacidad_util - peso_resto, 2)} kg libres",
                )
            )

        peso_actual = peso_resto + (
            prioritario_pedido.peso if prioritario_pedido is not None else 0.0
        )

    return PlanSalida(
        estrategia=EstrategiaReparto.MEJOR_ENCAGE,
        capacidad=capacidad,
        peso_total=peso_actual,
        seleccionados=seleccionados,
        descartados=descartados,
        prioritario=prioritario,
        milisegundos=cronometro.milisegundos,
    )


# --------------------------------------------------------------------------
# 3. Mochila 0/1 (programacion dinamica)
# --------------------------------------------------------------------------


def mochila_0_1(
    pedidos: Sequence[Pedido],
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
    objetivo: str = ObjetivoMochila.CANTIDAD,
) -> PlanSalida:
    """Mochila 0/1 por programacion dinamica. Solucion OPTIMA.

    Planteo del problema clasico: hay n objetos (los pedidos), cada uno con
    un peso (kg) y un valor (1 si el objetivo es maximizear cantidad, o el
    propio peso si es maximizar carga), y una mochila de capacidad C. Se
    busca el subconjunto de peso total <= C con el mayor valor posible, y
    cada objeto se puede tomar UNA sola vez (de ahi el "0/1").

    Definicion del problema de subproblema:

        T[i][c] = maximo valor alcanzable usando los pedidos 0..i-1
                  con una capacidad disponible de c centesimas

    Casos base:

        T[0][c] = 0            no hay pedidos, valor 0
        T[i][0] = 0            no hay capacidad, valor 0

    Transicion (la parte importante):

        T[i][c] = T[i-1][c]                                     si w[i-1] > c
        T[i][c] = max( T[i-1][c],  T[i-1][c-w[i-1]] + v[i-1] )  si w[i-1] <= c

        Es decir: o NO tomo el pedido i-1, o lo tomo y resuelvo el
        subproblema que le queda con la capacidad restante.

    La version ITERATIVA (esta) se construye por filas crecientes, y cada
    fila depende solo de la anterior. La version RECURSIVA con memorizacion
    daria el mismo resultado, pero la forma iterativa evita el costo de
    llamadas recursivas, que en Python es alto.

    Reconstruccion: la tabla guarda el valor maximo, pero no que camino se
    tomo. Por eso, al volver desde T[n][C] se compara T[i][c] con
    T[i-1][c]: si difieren, el pedido i-1 fue tomado y se retrocede en la
    capacidad; si son iguales, fue omitido. Esa comparacion reconstruye la
    solucion optima sin haber guardado decisiones adicionales.

    Complejidad: tiempo O(n * C) y memoria O(n * C), con C = capacidad en
    centesimas. Con la capacidad fija en 30 kg, C es una constante (3000), de
    modo que el algoritmo es O(n) respecto de la cantidad de pedidos, frente
    al O(n^2) de las heuristicas.

    Si se supera `MAX_PEDIDOS_MOCHILA`, la tabla ocuparia mas memoria del
    razonable y se degrada a Best-Fit, informandolo en el objetivo.
    """
    with Cronometro() as cronometro:
        if len(pedidos) > MAX_PEDIDOS_MOCHILA:
            plan = mejor_encaje(pedidos, capacidad, prioritario)
            plan.objetivo = (
                f"Degradado a Best-Fit: {len(pedidos)} pedidos exceden el "
                f"limite de {MAX_PEDIDOS_MOCHILA} para la tabla de la mochila"
            )
            return plan

        prioritario_pedido, resto, capacidad_util = _separar_prioritario(
            pedidos, capacidad, prioritario
        )

        pesos: List[int] = [int(pedido.peso_centavos) for pedido in resto]
        valores: List[int] = _valores(resto, objetivo)
        total = len(resto)
        limite = int(capacidad_util * ESCALA)

        filas: List[List[int]] = [[0] * (limite + 1) for _ in range(total + 1)]

        for i in range(1, total + 1):
            peso_actual = pesos[i - 1]
            valor_actual = valores[i - 1]
            fila_anterior = filas[i - 1]
            fila_actual = filas[i]

            for c in range(limite + 1):
                if peso_actual > c:
                    fila_actual[c] = fila_anterior[c]
                else:
                    sin_tomarlo = fila_anterior[c]
                    tomarlo = fila_anterior[c - peso_actual] + valor_actual
                    fila_actual[c] = sin_tomarlo if sin_tomarlo >= tomarlo else tomarlo

        elegidos = _reconstruir(filas, pesos, total, limite)

        seleccionados: List[Pedido] = []
        descartados: List[Descartado] = []
        peso_total = 0.0
        tomados = set(elegidos)

        if prioritario_pedido is not None:
            seleccionados.append(prioritario_pedido)
            peso_total += prioritario_pedido.peso

        for indice, pedido in enumerate(resto):
            if indice in tomados:
                seleccionados.append(pedido)
                peso_total += pedido.peso
            else:
                descartados.append(
                    Descartado(
                        pedido,
                        "fuera de la combinacion optima: incluirlo impediria "
                        "entregar mas pedidos",
                    )
                )

        seleccionados.sort(key=lambda pedido: pedido.peso, reverse=True)

    return PlanSalida(
        estrategia=EstrategiaReparto.MOCHILA_0_1,
        capacidad=capacidad,
        peso_total=peso_total,
        seleccionados=seleccionados,
        descartados=descartados,
        prioritario=prioritario,
        milisegundos=cronometro.milisegundos,
        objetivo=ObjetivoMochila.ETIQUETAS.get(objetivo, objetivo),
    )


def _valores(pedidos: Sequence[Pedido], objetivo: str) -> List[int]:
    """Valor asociado a cada pedido segun el objetivo de la mochila."""
    if objetivo == ObjetivoMochila.PESO:
        return [pedido.peso_centavos for pedido in pedidos]

    return [1 for pedido in pedidos]


def _reconstruir(
    filas: List[List[int]],
    pesos: List[int],
    total: int,
    limite: int,
) -> set:
    """Recupera el subconjunto optimo recorriendo la tabla hacia atras.

    Si T[i][c] es distinto de T[i-1][c], el pedido i-1 debio tomarse: de no
    ser asi, el valor de la fila i seria identico al de la fila i-1. Esa
    asercion es la que permite reconstruir la solucion sin haber guardado
    una tabla de decisiones adicional, ahorrando la mitad de la memoria.
    """
    elegidos = set()
    c = limite

    for i in range(total, 0, -1):
        if filas[i][c] != filas[i - 1][c]:
            elegidos.add(i - 1)
            c -= pesos[i - 1]

    return elegidos


# --------------------------------------------------------------------------
# Utilidad compartida
# --------------------------------------------------------------------------


def _separar_prioritario(
    pedidos: Sequence[Pedido], capacidad: float, prioritario: Optional[str]
) -> Tuple[Optional[Pedido], List[Pedido], float]:
    """Aparta el pedido prioritario y descuenta su peso de la capacidad.

    El pedido prioritario se carga siempre primero y se considera
    infacturable: si el usuario lo eligio, se lleva. Por eso no se evalua
    contra la capacidad, solo se reserva su peso. Si aun asi el pedido
    solo superara la capacidad del vehiculo, no habria una salida valida y
    se deja al llamador decidir.

    IMPORTANTE: la capacidad devuelta es la que QUEDA para el resto de los
    pedidos, ya con el prioritario descontado. Quien la use debe acumular
    el peso de los pedidos normales por separado y sumarle el del
    prioritario solo al final. De lo contrario el peso prioritario se
    descontaria dos veces y el vehiculo quedaria vacio a la mitad.
    """
    if prioritario is None:
        return None, list(pedidos), capacidad

    pedido = next((p for p in pedidos if p.codigo == prioritario), None)

    if pedido is None:
        return None, list(pedidos), capacidad

    resto = [p for p in pedidos if p.codigo != prioritario]
    return pedido, resto, round(capacidad - pedido.peso, 3)
