"""
 nucleo.repositorio
 ==================

 Almacenamiento de los pedidos y del historial de salidas.

 La version original de consola mantenia todo en variables globales en
 memoria, lo que hacia que al cerrar el programa se perdiera todo y que el
 contador de codigos volviera a 1. Aqui los datos viven en un diccionario
 y se respaldan en un archivo JSON.

 Dos detalles de ingenieria que conviene conocer:

 1. ESCRITURA ATOMICA. Se escribe primero en un archivo temporal y luego
    se renombra con `os.replace`. Si el programa se cierra a mitad de una
    escritura, el archivo original queda intacto en vez de corrupto. Es el
    patron "write to temp, then rename" y es la forma correcta de guardar
    estado en disco.

 2. CONTADOR PERSISTIDO. El codigo del proximo pedido se guarda en el JSON.
    Si no, al recargar se reiniciaria en P001 y se pisarian pedidos ya
    existentes.

 NUCLEO PURO en cuanto a la logica: no imprime, solo devuelve resultados.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .modelos import EstadoPedido, Pedido, Salida

VERSION_ARCHIVO = 1

# Carpeta del proyecto, deducida de la ubicacion de este archivo. Se usa para
# que los datos SIEMPRE se guarden en el mismo lugar, sin importar desde que
# carpeta se ejecute el programa: con una ruta relativa como "datos/pedidos.json"
# bastaba con lanzar `python app.py` desde otro directorio para crear una base
# de datos nueva y perder la anterior.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
ARCHIVO_POR_DEFECTO = RAIZ_PROYECTO / "datos" / "pedidos.json"


class Repositorio:
    """Persistencia en archivo JSON de pedidos e historial."""

    def __init__(self, ruta: Optional[str] = None) -> None:
        # Orden de prioridad: ruta explicita, variable de entorno, y por
        # ultimo la ruta por defecto del proyecto.
        # La variable de entorno sirve para alejar los datos en pruebas o en
        # una instalacion real sin tocar el codigo.
        self.ruta = Path(
            ruta or os.environ.get("RAPPIDOS_ARCHIVO") or ARCHIVO_POR_DEFECTO
        )
        self.pedidos: Dict[str, Pedido] = {}
        self.salidas: List[Salida] = []
        self.contador = 1
        self._cargar()

    # ---------------------------------------------------------------- carga

    def _cargar(self) -> None:
        """Lee el archivo si existe. Un archivo danio no tumba la app.

        Se captura la excepcion y se arranca con estado vacio: para una
        herramienta de coursework es preferible perder los datos a no
        poder arrancar.
        """
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
        self.salidas = [
            Salida(
                id=registro.get("id", indice + 1),
                codigos=list(registro.get("codigos", [])),
                peso_total=float(registro.get("peso_total", 0.0)),
                capacidad=float(registro.get("capacidad", 30.0)),
                cantidad=int(registro.get("cantidad", 0)),
                estrategia=str(registro.get("estrategia", "")),
                prioritario=registro.get("prioritario"),
                fecha=str(registro.get("fecha", "")),
            )
            for indice, registro in enumerate(datos.get("salidas", []))
        ]
        self.contador = int(datos.get("contador", self._siguiente_contador()))

    def _siguiente_contador(self) -> int:
        """Deduce el contador a partir del mayor codigo existente.

        Es la red de seguridad por si el JSON fue editado a mano y no tiene
        el campo `contador`: revisa todos los codigos y continua desde el
        mas alto, en vez de volver a P001.
        """
        if not self.pedidos:
            return 1

        mayor = 0
        for codigo in self.pedidos:
            try:
                mayor = max(mayor, int(str(codigo).lstrip("Pp")))
            except ValueError:
                continue

        return mayor + 1

    # --------------------------------------------------------------- guardado

    def guardar(self) -> None:
        """Persiste el estado completo de forma atomica."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)

        datos = {
            "version": VERSION_ARCHIVO,
            "contador": self.contador,
            "pedidos": {codigo: pedido.a_dict() for codigo, pedido in self.pedidos.items()},
            "salidas": [
                {
                    "id": salida.id,
                    "codigos": salida.codigos,
                    "peso_total": salida.peso_total,
                    "capacidad": salida.capacidad,
                    "cantidad": salida.cantidad,
                    "estrategia": salida.estrategia,
                    "prioritario": salida.prioritario,
                    "fecha": salida.fecha,
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

    # ---------------------------------------------------------------- lectura

    def listar(self, solo_pendientes: bool = False) -> List[Pedido]:
        """Devuelve los pedidos, opcionalmente solo los pendientes."""
        if solo_pendientes:
            return [p for p in self.pedidos.values() if p.pendiente]

        return list(self.pedidos.values())

    def obtener(self, codigo: str) -> Optional[Pedido]:
        """Devuelve el pedido con ese codigo, o None si no existe.

        Normaliza a mayusculas porque el usuario puede escribir "p001".
        """
        return self.pedidos.get(str(codigo).strip().upper())

    @property
    def siguiente_codigo(self) -> str:
        return f"P{self.contador:03d}"

    def avanzar_contador(self) -> str:
        """Reserva y devuelve el siguiente codigo disponible."""
        codigo = self.siguiente_codigo
        self.contador += 1
        return codigo

    # ---------------------------------------------------------------- escritura

    def agregar(self, pedido: Pedido) -> Pedido:
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
