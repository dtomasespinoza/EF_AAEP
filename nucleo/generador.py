"""Datos de prueba para los algoritmos."""

from __future__ import annotations

import random
from typing import List, Optional, Sequence

from .modelos import PESO_MAXIMO_KG, PESO_MINIMO_KG, Pedido

PREFIJOS = ["Calle", "Carrera", "Avenida", "Diagonal", "Circular", "Transversal"]

TIPOS_VIA = [
    "Las Flores", "Bolivar", "Juarez", "Libertadores", "San Juan",
    "Andes", "El Dorado", "Simón Bolívar", "NQS", "Jiménez", "Coba",
    "Ricaurte", "30", "45", "19", "80", "100", "Caribe", "Arenal",
    "Popayán", "Amazonas", "Río Calle", "Zarzal", "Versalles", "Pinar",
]

BARRIOS = [
    "La Castilla", "El Cedro", "La Flora", "San José", "La Estrada",
    "Belén", "Versalles", "La Granada", "Candelaria", "Santa Fe",
    "Las Américas", "Villa Hermosa", "Tunal", "Ciudad Jardín", "Portal",
]

NOMBRES = [
    "Ana", "Carlos", "María", "Juan", "Laura", "Andrés", "Sofía",
    "Diego", "Valentina", "Camilo", "Daniela", "Sebastián", "Camila",
    "Mateo", "Isabella", "Felipe", "Mariana", "Esteban", "Carolina",
    "Julián", "Fernanda", "Ricardo", "Paula", "Nicolás", "Daniela",
    "Alejandro", "Gabriela", "David", "Luisa", "Óscar", "Paola",
]

APELLIDOS = [
    "García", "Rodríguez", "Martínez", "Hernández", "López", "González",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Rivera",
    "Gómez", "Díaz", "Castro", "Ortiz", "Silva", "Rojas", "Mendoza",
    "Aguilar", "Castillo", "Morales", "Vargas", "Medina", "Navarro",
]

class GeneradorPedidos:
    """Fabrica de pedidos aleatorios con direcciones plausibles."""

    def __init__(self, semilla: Optional[int] = None) -> None:
        self.azar = random.Random(semilla)

    def peso_aleatorio(self) -> float:
        """Genera un peso sesgado hacia los valores bajos."""
        while True:
            candidato = self.azar.paretovariate(1.6)

            if candidato <= 1.0:
                peso = PESO_MINIMO_KG + candidato * 8.0
            else:
                peso = 8.0 + self.azar.expovariate(1 / 9.0)

            peso = round(peso, 2)

            if PESO_MINIMO_KG <= peso <= PESO_MAXIMO_KG:
                return peso

    def direccion_aleatoria(self) -> str:
        """Compone una direccion con formato de calle y barrio."""
        prefijo = self.azar.choice(PREFIJOS)
        tipo = self.azar.choice(TIPOS_VIA)
        numero = self.azar.randint(1, 199)

        letra = self.azar.choice(["", "A", "B", "C", "D", "E", "F"])
        sufijo = self.azar.choice(["", "", "", " bis", " este", " oeste"])
        barrio = self.azar.choice(BARRIOS)

        calle = f"{prefijo} {tipo} {numero}{letra}{sufijo}"
        return f"{calle}, {barrio}"

    def nombre_aleatorio(self) -> str:
        return f"{self.azar.choice(NOMBRES)} {self.azar.choice(APELLIDOS)}"

    def telefono_aleatorio(self) -> str:
        prefijo = self.azar.choice(["300", "301", "310", "320", "321", "350"])
        return f"{prefijo} {self.azar.randint(100, 999)} {self.azar.randint(1000, 9999)}"

    def crear(self, indice: int, codigo: str) -> Pedido:
        """Crea un pedido completo con todos sus campos."""
        return Pedido(
            codigo=codigo,
            peso=self.peso_aleatorio(),
            direccion=self.direccion_aleatoria(),
            cliente=self.nombre_aleatorio(),
            telefono=self.telefono_aleatorio(),
        )

    def generar(self, cantidad: int, codigos: Sequence[str]) -> List[Pedido]:
        """Genera `cantidad` pedidos usando los codigos recibidos."""
        pedidos = []

        for indice in range(cantidad):
            codigo = codigos[indice] if indice < len(codigos) else f"P{indice + 1:03d}"
            pedidos.append(self.crear(indice, codigo))

        return pedidos

def generar_pedidos(cantidad: int, codigos: Sequence[str], semilla: Optional[int] = None) -> List[Pedido]:
    """Atajo funcional: crea el generador y produce los pedidos."""
    return GeneradorPedidos(semilla).generar(cantidad, codigos)
