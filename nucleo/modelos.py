"""Pedidos, salidas y opciones del sistema."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

PESO_MINIMO_KG = 0.1
PESO_MAXIMO_KG = 30.0
CAPACIDAD_VEHICULO_KG = 30.0
PREFIJO_CODIGO = "P"
DIGITOS_CODIGO = 3

class EstadoPedido(Enum):
    """Ciclo de vida de un pedido dentro del sistema."""

    PENDIENTE = "PENDIENTE"
    DESPACHADO = "DESPACHADO"

    @classmethod
    def desde_texto(cls, texto: str) -> "EstadoPedido":
        normalizado = (texto or "").strip().upper()
        for estado in cls:
            if estado.value == normalizado:
                return estado
        return cls.PENDIENTE

class EstrategiaOrden(Enum):
    """Algoritmos de ordenamiento disponibles para comparar."""

    BURBUJA = "BURBUJA"
    INSERCION = "INSERCION"
    QUICKSORT = "QUICKSORT"
    CONTEO = "CONTEO"
    CUBETAS = "CUBETAS"
    NATIVO = "NATIVO"

    @property
    def etiqueta(self) -> str:
        return {
            EstrategiaOrden.BURBUJA: "Burbuja",
            EstrategiaOrden.INSERCION: "Insercion",
            EstrategiaOrden.QUICKSORT: "QuickSort",
            EstrategiaOrden.CONTEO: "Conteo",
            EstrategiaOrden.CUBETAS: "Cubetas",
            EstrategiaOrden.NATIVO: "Nativo (sorted)",
        }[self]

class CampoOrden(Enum):
    """CAMPO por el que se ordena el listado de pedidos."""

    CODIGO = "CODIGO"
    PESO = "PESO"
    DISTRITO = "DISTRITO"

    @property
    def etiqueta(self) -> str:
        return {
            CampoOrden.CODIGO: "Codigo",
            CampoOrden.PESO: "Peso",
            CampoOrden.DISTRITO: "Distrito",
        }[self]

    @property
    def admite_algoritmo(self) -> bool:
        """Solo el peso se ordena con los algoritmos propios del curso."""
        return self is CampoOrden.PESO

class EstrategiaReparto(Enum):
    """Estrategias para elegir que pedidos caben en el vehiculo."""

    PRIMERO_QUE_CABE = "PRIMERO_QUE_CABE"
    MEJOR_ENCAGE = "MEJOR_ENCAGE"
    MOCHILA_0_1 = "MOCHILA_0_1"

    @property
    def etiqueta(self) -> str:
        return {
            EstrategiaReparto.PRIMERO_QUE_CABE: "Primero que cabe",
            EstrategiaReparto.MEJOR_ENCAGE: "Mejor encaje",
            EstrategiaReparto.MOCHILA_0_1: "Mochila 0/1 (optimo)",
        }[self]

    @property
    def descripcion(self) -> str:
        return {
            EstrategiaReparto.PRIMERO_QUE_CABE: (
                "Ordena de mayor a menor y toma el primer pedido que cabe. "
                "Rapido, pero deja espacio inutilizado."
            ),
            EstrategiaReparto.MEJOR_ENCAGE: (
                "Ordena de mayor a menor y elige el pedido que deja el menor "
                "espacio libre. Mejor aprovechamiento que First-Fit."
            ),
            EstrategiaReparto.MOCHILA_0_1: (
                "Programacion dinamica: garantiza la maxima cantidad de "
                "pedidos entregados. Es la version optima."
            ),
        }[self]

@dataclass
class Pedido:
    """Un pedido registrado en el sistema."""

    codigo: str
    peso: float
    direccion: str = ""
    cliente: str = ""
    telefono: str = ""
    distrito: str = ""
    prioridad: bool = False
    estado: EstadoPedido = EstadoPedido.PENDIENTE
    fecha_registro: str = ""
    fecha_despacho: str = ""

    @property
    def peso_centavos(self) -> int:
        """Peso expresado en centesimas de kilogramo (entero exacto)."""
        return int(round(self.peso * 100))

    @property
    def pendiente(self) -> bool:
        return self.estado is EstadoPedido.PENDIENTE

    def a_dict(self) -> Dict[str, Any]:
        datos = asdict(self)
        datos["estado"] = self.estado.value
        datos["pendiente"] = self.pendiente
        return datos

    @classmethod
    def desde_dict(cls, datos: Dict[str, Any]) -> "Pedido":
        return cls(
            codigo=str(datos.get("codigo", "")),
            peso=float(datos.get("peso", 0.0)),
            direccion=str(datos.get("direccion", "")),
            cliente=str(datos.get("cliente", "")),
            telefono=str(datos.get("telefono", "")),
            distrito=str(datos.get("distrito", "")),
            prioridad=bool(datos.get("prioridad", False)),
            estado=EstadoPedido.desde_texto(datos.get("estado", "PENDIENTE")),
            fecha_registro=str(datos.get("fecha_registro", "")),
            fecha_despacho=str(datos.get("fecha_despacho", "")),
        )

    @property
    def distrito_efectivo(self) -> str:
        """Distrito con respaldo para los datos anteriores al campo."""
        if self.distrito.strip():
            return self.distrito.strip()

        if "," in self.direccion:
            return self.direccion.rsplit(",", 1)[-1].strip()

        return ""

@dataclass
class Salida:
    """Registro de una salida confirmada. Es el historial del sistema."""

    id: int
    codigos: List[str] = field(default_factory=list)
    peso_total: float = 0.0
    capacidad: float = CAPACIDAD_VEHICULO_KG
    cantidad: int = 0
    estrategia: str = ""
    prioritario: Optional[str] = None
    fecha: str = ""
    detalle: List[Dict[str, Any]] = field(default_factory=list)

    viajes: int = 1

    @property
    def ocupacion(self) -> float:
        if self.capacidad <= 0:
            return 0.0
        return round(self.peso_total / (self.capacidad * max(self.viajes, 1)) * 100, 2)

    def a_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "codigos": list(self.codigos),
            "peso_total": self.peso_total,
            "capacidad": self.capacidad,
            "cantidad": self.cantidad,
            "estrategia": self.estrategia,
            "prioritario": self.prioritario,
            "fecha": self.fecha,
            "detalle": list(self.detalle),
            "viajes": self.viajes,
            "ocupacion": self.ocupacion,
        }

    @classmethod
    def desde_dict(cls, datos: Dict[str, Any], identificador: int = 0) -> "Salida":
        """Reconstruye una salida desde el JSON."""
        return cls(
            id=int(datos.get("id", identificador)),
            codigos=[str(codigo) for codigo in datos.get("codigos", [])],
            peso_total=float(datos.get("peso_total", 0.0)),
            capacidad=float(datos.get("capacidad", CAPACIDAD_VEHICULO_KG)),
            cantidad=int(datos.get("cantidad", 0)),
            estrategia=str(datos.get("estrategia", "")),
            prioritario=datos.get("prioritario"),
            fecha=str(datos.get("fecha", "")),
            detalle=list(datos.get("detalle", []) or []),
            viajes=int(datos.get("viajes", 1)),
        )

@dataclass
class ResultadoOperacion:
    """Respuesta uniforme de todos los casos de uso del servicio."""

    ok: bool
    mensaje: str = ""
    datos: Optional[Any] = None

    @classmethod
    def exito(cls, mensaje: str = "", datos: Any = None) -> "ResultadoOperacion":
        return cls(True, mensaje, datos)

    @classmethod
    def error(cls, mensaje: str, datos: Any = None) -> "ResultadoOperacion":
        return cls(False, mensaje, datos)

def ahora() -> str:
    """Marca de tiempo legible y ordenable lexicograficamente."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
