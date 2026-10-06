"""Planificacion de mochilas por distrito."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .algoritmos import Cronometro, ordenar
from .modelos import CAPACIDAD_VEHICULO_KG, EstrategiaOrden, EstrategiaReparto, Pedido

MAX_PEDIDOS_MOCHILA = 800

ESCALA = 100

class ObjetivoMochila:
    """Criterio a maximizar en la mochila 0/1."""

    CANTIDAD = "CANTIDAD"
    PESO = "PESO"

    ETIQUETAS = {
        CANTIDAD: "Maximo numero de pedidos",
        PESO: "Maximo peso transportado",
    }

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
            "distrito": self.pedido.distrito_efectivo,
            "cliente": self.pedido.cliente,
            "motivo": self.motivo,
        }

@dataclass
class Viaje:
    """UNA carga completa del vehiculo."""

    numero: int
    pedidos: List[Pedido] = field(default_factory=list)
    peso_total: float = 0.0
    capacidad: float = CAPACIDAD_VEHICULO_KG
    estrategia: Optional[EstrategiaReparto] = None

    @property
    def cantidad(self) -> int:
        return len(self.pedidos)

    @property
    def disponible(self) -> float:
        return round(self.capacidad - self.peso_total, 3)

    @property
    def ocupacion(self) -> float:
        if self.capacidad <= 0:
            return 0.0
        return round(self.peso_total / self.capacidad * 100, 2)

    def a_dict(self) -> Dict[str, Any]:
        return {
            "numero": self.numero,
            "cantidad": self.cantidad,
            "peso_total": round(self.peso_total, 2),
            "capacidad": self.capacidad,
            "disponible": self.disponible,
            "ocupacion": self.ocupacion,
            "estrategia": self.estrategia.value if self.estrategia else "",
            "estrategia_etiqueta": self.estrategia.etiqueta if self.estrategia else "",
            "pedidos": [p.a_dict() for p in self.pedidos],
        }

@dataclass
class PlanCarga:
    """Conjunto de viajes que cubre lo que se puede despachar de una vez."""

    viajes: List[Viaje] = field(default_factory=list)
    estrategia: Optional[EstrategiaReparto] = None
    capacidad: float = CAPACIDAD_VEHICULO_KG
    objetivo: str = ""
    no_asignados: List[Descartado] = field(default_factory=list)
    milisegundos: float = 0.0

    @property
    def total_pedidos(self) -> int:
        return sum(viaje.cantidad for viaje in self.viajes)

    @property
    def peso_total(self) -> float:
        return round(sum(viaje.peso_total for viaje in self.viajes), 2)

    @property
    def capacidad_total(self) -> float:
        return round(self.capacidad * len(self.viajes), 2)

    @property
    def ocupacion(self) -> float:
        """Ocupacion GLOBAL de todos los viajes juntos."""
        total = self.capacidad_total
        if total <= 0:
            return 0.0
        return round(self.peso_total / total * 100, 2)

    def recalcular_totales(self) -> None:
        """Renumera los viajes y recalcula los totales tras un recorte."""
        for indice, viaje in enumerate(self.viajes, start=1):
            viaje.numero = indice
            viaje.peso_total = round(sum(p.peso for p in viaje.pedidos), 2)

    def a_dict(self) -> Dict[str, Any]:
        return {
            "viajes": [viaje.a_dict() for viaje in self.viajes],
            "estrategia": self.estrategia.value if self.estrategia else "",
            "estrategia_etiqueta": self.estrategia.etiqueta if self.estrategia else "",
            "capacidad": self.capacidad,
            "capacidad_total": self.capacidad_total,
            "cantidad_viajes": len(self.viajes),
            "total_pedidos": self.total_pedidos,
            "peso_total": self.peso_total,
            "ocupacion": self.ocupacion,
            "objetivo": self.objetivo,
            "milisegundos": round(self.milisegundos, 3),
            "no_asignados": [d.a_dict() for d in self.no_asignados],
        }

@dataclass
class PlanSalida:
    """Plan de carga propuesto. Todavia NO modifica el sistema."""

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

def planear_salida(
    pedidos: Sequence[Pedido],
    estrategia: EstrategiaReparto = EstrategiaReparto.PRIMERO_QUE_CABE,
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
    objetivo: str = ObjetivoMochila.CANTIDAD,
) -> PlanSalida:
    """Genera un plan de carga con la estrategia indicada."""
    ordenados = sorted(pedidos, key=lambda p: (_clave_distrito(p), p.codigo))
    if not ordenados:
        return PlanSalida(estrategia=estrategia, capacidad=capacidad)

    primero = next((p for p in ordenados if p.codigo == prioritario), ordenados[0])
    distrito = _clave_distrito(primero)
    grupo = [p for p in ordenados if _clave_distrito(p) == distrito]
    otros = [p for p in ordenados if _clave_distrito(p) != distrito]

    if estrategia is EstrategiaReparto.MOCHILA_0_1:
        plan = mochila_0_1(grupo, capacidad, prioritario, objetivo)
    elif estrategia is EstrategiaReparto.MEJOR_ENCAGE:
        plan = mejor_encaje(grupo, capacidad, prioritario)
    else:
        plan = primero_que_cabe(grupo, capacidad, prioritario)

    plan.descartados.extend(
        Descartado(p, "se prepara en otra mochila por pertenecer a otro distrito")
        for p in otros
    )
    return plan

def _normalizar_distrito(texto: str) -> str:
    """Pone un distrito en minusculas y sin acentos, para agrupar bien."""
    limpio = str(texto or "").strip().lower()

    for acento, base in (("á", "a"), ("é", "e"), ("í", "i"),
                         ("ó", "o"), ("ú", "u"), ("ü", "u"), ("ñ", "n")):
        limpio = limpio.replace(acento, base)

    return " ".join(limpio.split())

def _clave_distrito(pedido: Pedido) -> str:
    distrito = _normalizar_distrito(pedido.distrito_efectivo)

    return distrito or f"sin distrito: {pedido.codigo}"

def planear_multi_viaje(
    pedidos: Sequence[Pedido],
    estrategia: EstrategiaReparto = EstrategiaReparto.MOCHILA_0_1,
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
    objetivo: str = ObjetivoMochila.CANTIDAD,
    maximo_viajes: Optional[int] = None,
) -> PlanCarga:
    """Prepara cargas por distrito hasta cubrir los pedidos o alcanzar el limite."""
    with Cronometro() as cronometro:
        disponibles = list(pedidos)
        viajes = []
        no_asignados = []
        objetivo_texto = ""

        while disponibles and (maximo_viajes is None or len(viajes) < maximo_viajes):
            plan = planear_salida(disponibles, estrategia, capacidad, prioritario, objetivo)
            if not objetivo_texto or "Degradado" in plan.objetivo:
                objetivo_texto = plan.objetivo

            if not plan.seleccionados:
                primero = min(disponibles, key=lambda p: (_clave_distrito(p), p.codigo))
                primero = next((p for p in disponibles if p.codigo == prioritario), primero)
                grupo = [p for p in disponibles if _clave_distrito(p) == _clave_distrito(primero)]
                no_asignados.extend(
                    Descartado(p, f"supera la capacidad de {capacidad:g} kg") for p in grupo
                )
                codigos = {p.codigo for p in grupo}
            else:
                viajes.append(Viaje(
                    numero=len(viajes) + 1,
                    pedidos=list(plan.seleccionados),
                    peso_total=round(plan.peso_total, 2),
                    capacidad=capacidad,
                    estrategia=estrategia,
                ))
                codigos = {p.codigo for p in plan.seleccionados}

            disponibles = [p for p in disponibles if p.codigo not in codigos]
            if prioritario in codigos:
                prioritario = None

        no_asignados.extend(
            Descartado(p, f"fuera del limite de {maximo_viajes} viajes") for p in disponibles
        )

    return PlanCarga(
        viajes=viajes, estrategia=estrategia, capacidad=capacidad,
        objetivo=objetivo_texto, no_asignados=no_asignados,
        milisegundos=cronometro.milisegundos,
    )

def planear_viajes(
    pedidos: Sequence[Pedido],
    viajes: int = 1,
    estrategia: EstrategiaReparto = EstrategiaReparto.MOCHILA_0_1,
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
    objetivo: str = ObjetivoMochila.CANTIDAD,
) -> PlanCarga:
    """Reparte los pendientes en un numero EXACTO de viajes."""
    return planear_multi_viaje(
        pedidos, estrategia, capacidad, prioritario, objetivo,
        maximo_viajes=max(viajes, 1),
    )

def comparar_estrategias(
    pedidos: Sequence[Pedido],
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
    objetivo: str = ObjetivoMochila.CANTIDAD,
) -> List[PlanSalida]:
    """Corre las tres estrategias sobre los mismos pedidos."""
    planes = []

    for estrategia in EstrategiaReparto:
        planes.append(
            planear_salida(pedidos, estrategia, capacidad, prioritario, objetivo)
        )

    return planes

def primero_que_cabe(
    pedidos: Sequence[Pedido],
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
) -> PlanSalida:
    """First-Fit Decreasing."""
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

def mejor_encaje(
    pedidos: Sequence[Pedido],
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
) -> PlanSalida:
    """Best-Fit Decreasing."""
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

def mochila_0_1(
    pedidos: Sequence[Pedido],
    capacidad: float = CAPACIDAD_VEHICULO_KG,
    prioritario: Optional[str] = None,
    objetivo: str = ObjetivoMochila.CANTIDAD,
) -> PlanSalida:
    """Mochila 0/1 por programacion dinamica. Solucion OPTIMA."""
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
    """Recupera el subconjunto optimo recorriendo la tabla hacia atras."""
    elegidos = set()
    c = limite

    for i in range(total, 0, -1):
        if filas[i][c] != filas[i - 1][c]:
            elegidos.add(i - 1)
            c -= pesos[i - 1]

    return elegidos

def _separar_prioritario(
    pedidos: Sequence[Pedido], capacidad: float, prioritario: Optional[str]
) -> Tuple[Optional[Pedido], List[Pedido], float]:
    """Aparta el pedido prioritario y descuenta su peso de la capacidad."""
    if prioritario is None:
        return None, list(pedidos), capacidad

    pedido = next((p for p in pedidos if p.codigo == prioritario), None)

    if pedido is None:
        return None, list(pedidos), capacidad

    resto = [p for p in pedidos if p.codigo != prioritario]
    return pedido, resto, round(capacidad - pedido.peso, 3)
