"""Conversion de resultados a respuestas JSON."""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

def serializar(objeto: Any) -> Any:
    """Convierte cualquier objeto del nucleo a algo que JSON acepte."""
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
    """Construye el sobre estandar de la API."""
    return {
        "exito": bool(exito),
        "mensaje": str(mensaje),
        "datos": serializar(datos),
    }
