"""Modulo prueba_distritos."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nucleo.modelos import EstrategiaReparto, Pedido
from nucleo.reparto import planear_multi_viaje, planear_salida, planear_viajes

class PruebaDistritos(unittest.TestCase):
    def pedido(self, numero, peso, distrito):
        return Pedido(codigo=f"P{numero:03d}", peso=peso, distrito=distrito)

    def test_distritos_distintos_no_comparten_mochila(self):
        pedidos = [self.pedido(1, 2, "Miraflores"), self.pedido(2, 3, "Comas")]
        for estrategia in EstrategiaReparto:
            with self.subTest(estrategia=estrategia):
                plan = planear_multi_viaje(pedidos, estrategia)
                self.assertEqual(len(plan.viajes), 2)
                self.assertEqual(plan.total_pedidos, 2)
                self.assertFalse(plan.no_asignados)

    def test_capacidad_y_variantes_del_mismo_distrito(self):
        pedidos = [
            self.pedido(1, 20, "Jesús María"),
            self.pedido(2, 15, " jesus   maria "),
            self.pedido(3, 10, "JESUS MARIA"),
            self.pedido(4, 5, "Comas"),
        ]
        for estrategia in EstrategiaReparto:
            plan = planear_multi_viaje(pedidos, estrategia)
            self.assertEqual(plan.total_pedidos, 4)
            self.assertEqual(len(plan.viajes), 3)
            self.assertTrue(all(v.peso_total <= 30 for v in plan.viajes))
            for viaje in plan.viajes:
                codigos = {p.codigo for p in viaje.pedidos}
                self.assertFalse("P004" in codigos and len(codigos) > 1)

    def test_prioritario_y_limite(self):
        pedidos = [self.pedido(1, 2, "Comas"), self.pedido(2, 3, "Surco")]
        plan = planear_viajes(pedidos, 1, prioritario="P002")
        self.assertEqual([p.codigo for p in plan.viajes[0].pedidos], ["P002"])
        self.assertEqual([p.pedido.codigo for p in plan.no_asignados], ["P001"])
        individual = planear_salida(pedidos, prioritario="P002")
        self.assertEqual([p.codigo for p in individual.seleccionados], ["P002"])

    def test_optimiza_dentro_del_distrito(self):
        pedidos = [self.pedido(i, peso, "Surco") for i, peso in enumerate([20, 15, 10], 1)]
        plan = planear_salida(pedidos, EstrategiaReparto.MOCHILA_0_1, objetivo="PESO")
        self.assertEqual(plan.peso_total, 30)

    def test_sin_distrito_no_presupone_ubicacion_comun(self):
        plan = planear_multi_viaje([self.pedido(1, 1, ""), self.pedido(2, 1, "")])
        self.assertEqual(len(plan.viajes), 2)

    def test_todos_los_viajes_sin_limite_oculto(self):
        pedidos = [self.pedido(i, 1, f"Distrito {i}") for i in range(1, 61)]
        plan = planear_multi_viaje(pedidos)
        self.assertEqual(len(plan.viajes), 60)
        self.assertEqual(plan.total_pedidos, 60)
        self.assertFalse(plan.no_asignados)

if __name__ == "__main__":
    unittest.main()
