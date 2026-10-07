"""Lectura y guardado de pedidos y salidas."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .costos import TARIFAS_INICIALES
from .modelos import EstadoPedido, Pedido, Salida

VERSION_ARCHIVO = 1

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
ARCHIVO_POR_DEFECTO = RAIZ_PROYECTO / "datos" / "pedidos.json"

class Repositorio:
    """Persistencia en archivo JSON de pedidos e historial."""

    def __init__(self, ruta: Optional[str] = None) -> None:

        self.ruta = Path(
            ruta or os.environ.get("RAPPIDOS_ARCHIVO") or ARCHIVO_POR_DEFECTO
        )
        self.pedidos: Dict[str, Pedido] = {}
        self.salidas: List[Salida] = []
        self.contador = 1
        self.tarifas = dict(TARIFAS_INICIALES)
        self._cargar()

    def _cargar(self) -> None:
        """Lee el archivo si existe. Un archivo danio no tumba la app."""
        if not self.ruta.exists():
            return

        try:
            with open(self.ruta, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
        except (json.JSONDecodeError, OSError):
            self.pedidos = {}
            self.salidas = []
            self.contador = 1
            return

        self.pedidos = {
            codigo: Pedido.desde_dict(valores)
            for codigo, valores in datos.get("pedidos", {}).items()
        }
        self.tarifas = dict(datos.get("tarifas", TARIFAS_INICIALES))
        for pedido in self.pedidos.values():
            pedido.tarifas = self.tarifas
        self.salidas = [
            Salida.desde_dict(registro, indice + 1)
            for indice, registro in enumerate(datos.get("salidas", []))
        ]
        self.contador = int(datos.get("contador", self._siguiente_contador()))

    def _siguiente_contador(self) -> int:
        """Deduce el contador a partir del mayor codigo existente."""
        if not self.pedidos:
            return 1

        mayor = 0
        for codigo in self.pedidos:
            try:
                mayor = max(mayor, int(str(codigo).lstrip("Pp")))
            except ValueError:
                continue

        return mayor + 1

    def guardar(self) -> None:
        """Persiste el estado completo de forma atomica."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)

        datos = {
            "version": VERSION_ARCHIVO,
            "tarifas": self.tarifas,
            "contador": self.contador,
            "pedidos": {codigo: pedido.a_dict() for codigo, pedido in self.pedidos.items()},

            "salidas": [
                {
                    clave: valor
                    for clave, valor in salida.a_dict().items()
                    if clave != "ocupacion"
                }
                for salida in self.salidas
            ],
        }

        directorio = self.ruta.parent
        descriptor, ruta_temporal = tempfile.mkstemp(dir=directorio, suffix=".tmp")

        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
                json.dump(datos, archivo, ensure_ascii=False, indent=2)
                archivo.flush()
                os.fsync(archivo.fileno())
            os.replace(ruta_temporal, self.ruta)
        except BaseException:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
            raise

    def listar(self, solo_pendientes: bool = False) -> List[Pedido]:
        """Devuelve los pedidos, opcionalmente solo los pendientes."""
        if solo_pendientes:
            return [p for p in self.pedidos.values() if p.pendiente]

        return list(self.pedidos.values())

    def obtener(self, codigo: str) -> Optional[Pedido]:
        """Devuelve el pedido con ese codigo, o None si no existe."""
        return self.pedidos.get(str(codigo).strip().upper())

    @property
    def siguiente_codigo(self) -> str:
        return f"P{self.contador:03d}"

    def avanzar_contador(self) -> str:
        """Reserva y devuelve el siguiente codigo disponible."""
        codigo = self.siguiente_codigo
        self.contador += 1
        return codigo

    def agregar(self, pedido: Pedido) -> Pedido:
        pedido.tarifas = self.tarifas
        self.pedidos[pedido.codigo] = pedido
        return pedido

    def eliminar(self, codigo: str) -> bool:
        """Elimina un pedido. Devuelve si existia."""
        return self.pedidos.pop(str(codigo).strip().upper(), None) is not None

    def vaciar_pendientes(self) -> int:
        """Elimina todos los pedidos pendientes. Devuelve cuantos eran."""
        codigos = [codigo for codigo, p in self.pedidos.items() if p.pendiente]

        for codigo in codigos:
            del self.pedidos[codigo]

        return len(codigos)

    def registrar_salida(self, salida: Salida) -> Salida:
        self.salidas.append(salida)
        return salida

    def limpiar_todo(self) -> None:
        """Borra pedidos e historial, y reinicia el contador."""
        self.pedidos = {}
        self.salidas = []
        self.contador = 1

    def estadisticas_almacen(self) -> Dict[str, Any]:
        """Resumen del estado guardado en disco."""
        return {
            "total": len(self.pedidos),
            "pendientes": sum(1 for p in self.pedidos.values() if p.pendiente),
            "despachados": sum(1 for p in self.pedidos.values() if p.estado is EstadoPedido.DESPACHADO),
            "salidas": len(self.salidas),
            "ruta": str(self.ruta),
            "contador": self.contador,
        }
