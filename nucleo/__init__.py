"""
 nucleo
 ======

 Nucleo de RAPPIDOS: todo el dominio, los algoritmos y la persistencia.

 La REGLA de arquitectura del proyecto es que este paquete NO importa nada
 de las interfaces. No conoce `input`, `print`, Flask ni HTML. Todo lo que
 entra sale por funciones que devuelven estructuras de datos.

 Esto permite que la misma logica se use desde la version de consola y desde
 la version web sin duplicar una sola linea de negocio.
"""

from .modelos import (
    CAPACIDAD_VEHICULO_KG,
    PESO_MAXIMO_KG,
    PESO_MINIMO_KG,
    CampoOrden,
    EstadoPedido,
    EstrategiaOrden,
    EstrategiaReparto,
    Pedido,
    ResultadoOperacion,
    Salida,
)
from .reparto import ObjetivoMochila, PlanCarga, PlanSalida, Viaje
from .servicio import RAPPIDOS

__all__ = [
    "RAPPIDOS",
    "Pedido",
    "Salida",
    "PlanSalida",
    "PlanCarga",
    "Viaje",
    "ResultadoOperacion",
    "EstadoPedido",
    "CampoOrden",
    "EstrategiaOrden",
    "EstrategiaReparto",
    "ObjetivoMochila",
    "CAPACIDAD_VEHICULO_KG",
    "PESO_MINIMO_KG",
    "PESO_MAXIMO_KG",
]
