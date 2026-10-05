"""
 nucleo.serializador
 ===================

 Conversion de los objetos del nucleo a estructuras de JSON.

 Hace falta porque el nucleo devuelve dataclasses (Pedido, PlanSalida,
 Salida), que son comodos de usar en Python pero no se pueden pasar
 directamente a `jsonify` de Flask. Este modulo es el unico lugar del
 proyecto que conoce el formato de la respuesta: si manana la API cambia,
 se cambia aqui y el nucleo ni se entera.

 La conversion es RECURSIVA: si un campo contiene una lista de objetos, se
 aplica a cada elemento. Asi agregar un campo anidado no obliga a tocar
 los llamadores.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any


def serializar(objeto: Any) -> Any:
    """Convierte cualquier objeto del nucleo a algo que JSON acepte.

    Reglas, en orden:
        1. Si el objeto tiene `a_dict`, se delego en ese metodo.
        2. Si es un dataclass, se usan sus campos.
        3. Si es un Enum, se usa su valor.
        4. Si es una lista o tupla, se aplica a cada elemento.
        5. Si es un dict, se convierte clave y valor.
        6. Cualquier otro valor se devuelve tal cual: `jsonify` sabe
           manejar numeros, cadenas, booleanos y None.
    """
    if objeto is None or isinstance(objeto, (str, int, float, bool)):
        return objeto

    if hasattr(objeto, "a_dict") and callable(objeto.a_dict):
        return serializar(objeto.a_dict())

    if dataclasses.is_dataclass(objeto) and not isinstance(objeto, type):
        return serializar(dataclasses.asdict(objeto))

    if isinstance(objeto, Enum):
        return serializar(objeto.value)

    if isinstance(objeto, (list, tuple, set)):
        return [serializar(elemento) for elemento in objeto]

    if isinstance(objeto, dict):
        return {str(clave): serializar(valor) for clave, valor in objeto.items()}

    return str(objeto)


def respuesta(exito: bool, mensaje: str = "", datos: Any = None) -> dict:
    """Construye el sobre estandar de la API.

    Toda respuesta tiene la misma forma: `exito`, `mensaje` y `datos`. El
    cliente (JavaScript) no necesita preguntar de que tipo es la respuesta:
    siempre mira `exito` primero. Esa uniformidad evita try/except en el
    JavaScript.
    """
    return {
        "exito": bool(exito),
        "mensaje": str(mensaje),
        "datos": serializar(datos),
    }
