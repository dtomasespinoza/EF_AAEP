"""
 nucleo.modelos
 =============

 Modelos de dominio de RAPPIDOS. Este modulo es NUCLEO PURO: no conoce la
 interfaz de usuario (ni input/print, ni Flask, ni HTML). Solo define datos.

 Se usan dataclasses porque son la forma estandar de la biblioteca (PEP 557)
 para modelar entidades, y porque `dataclasses.asdict` permite serializar a
 JSON sin escribir el mapeo a mano.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------
# Constantes del dominio
# --------------------------------------------------------------------------

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
    NATIVO = "NATIVO"  # sorted() de Python, como linea base

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
    """CAMPO por el que se ordena el listado de pedidos.

    Antes solo se podia ordenar por peso, porque el unico dato numerico era
    ese. Al separar el distrito de la direccion aparece un segundo criterio
    util, y el codigo es el tercero porque es el orden natural de lectura de
    una lista de pedidos.

    El peso sigue siendo el unico campo con ELECCION DE ALGORITMO: los otros
    dos se ordenan con el comparador nativo. La razon es que el conteo y las
    cubetas dependen de que los valores sean enteros dentro de un rango
    acotado, y el codigo ("P001") o el distrito ("La Castilla") no cumplen
    esa precondicion. Forzarles un algoritmo incompatible seria un error de
    diseño, no una optimizacion.
    """

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

    PRIMERO_QUE_CABE = "PRIMERO_QUE_CABE"  # First-Fit Decreasing
    MEJOR_ENCAGE = "MEJOR_ENCAGE"  # Best-Fit Decreasing
    MOCHILA_0_1 = "MOCHILA_0_1"  # Knapsack dinamico (optimo)

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


# --------------------------------------------------------------------------
# Entidades
# --------------------------------------------------------------------------


@dataclass
class Pedido:
    """Un pedido registrado en el sistema.

    Se conserva `peso` en kg con decimales, y se agrega `peso_centavos`
    (entero) porque los algoritmos de conteo y las tablas de programacion
    dinamica requieren indices enteros: mezclar floats como indices produce
    errores de redondeo.
    """

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
        """Distrito con respaldo para los datos anteriores al campo.

        Los pedidos guardados antes de separar el distrito no tienen esta
        columna. En vez de mostrarlos todos como "Sin distrito", se les
        deduce del texto que sigue a la ultima coma de la direccion, que es
        justo donde el barrio estaba escrito. Asi la agrupacion por distrito
        funciona desde el primer dia sin obligar a reimportar nada.
        """
        if self.distrito.strip():
            return self.distrito.strip()

        if "," in self.direccion:
            return self.direccion.rsplit(",", 1)[-1].strip()

        return ""


@dataclass
class Salida:
    """Registro de una salida confirmada. Es el historial del sistema.

    Guarda los codigos de los pedidos despachados Y una COPIA de sus datos
    (peso, distrito, direccion y cliente) en `detalle`.

    Existe esa copia por un motivo concreto: sin ella, el historial solo
    permite saber CUANTOS pedidos salieron y cuanto pesaban, pero no que
    llevo cada uno. Reconstruir el detalletendria que buscar los codigos en
    el almacen, y un pedido puede haberse editado o eliminado despues, con
    lo que el historial mostraria datos que ya no corresponden a lo que
    realmente salio ese dia. Guardar la copia al confirmar es lo que hace
    que el historial sea una fuente de verdad y no una referencia fragile.
    """

    id: int
    codigos: List[str] = field(default_factory=list)
    peso_total: float = 0.0
    capacidad: float = CAPACIDAD_VEHICULO_KG
    cantidad: int = 0
    estrategia: str = ""
    prioritario: Optional[str] = None
    fecha: str = ""
    detalle: List[Dict[str, Any]] = field(default_factory=list)
    #: Cantidad de viajes que confirmo esta misma operacion. Un plan
    #: multi-viaje despacha varios viajes de una vez, asi que una salida
    #: puede corresponder a mas de un viaje.
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
        """Reconstruye una salida desde el JSON.

        Los campos `detalle` y `viajes` no existen en los archivos guardados
        antes de esta version, asi que se usan valores por defecto. Sin eso,
        una salida antigua impediria arrancar la aplicacion al no encontrar
        las claves.
        """
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
    """Respuesta uniforme de todos los casos de uso del servicio.

    Evita que las funciones launchen excepciones hacia la interfaz: la UI
    solo necesita leer `ok` y `mensaje`, sin try/except disperso.
    """

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
