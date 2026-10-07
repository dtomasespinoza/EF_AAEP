import unittest
from nucleo.modelos import Pedido, Salida
from nucleo.reparto import planear_multi_viaje
from nucleo.costos import cotizar

class PruebaCostos(unittest.TestCase):
    def test_tarifas_y_normalizacion(self):
        for distrito, tarifa in [("San Isidro", 2), ("Surco", 2), ("Santiago de Surco", 2), ("Los Olivos", 4), ("Independencia", 4), (" JESÚS   MARÍA ", 3)]:
            with self.subTest(distrito=distrito):
                self.assertEqual(cotizar(2.5, distrito)["costo_envio"], 2.5 * tarifa)
        self.assertEqual(cotizar(1.005, "Surco")["costo_envio"], 2.01)

    def test_edicion_y_direccion_antigua(self):
        p = Pedido("P001", 3, direccion="Av. Lima, Surco")
        self.assertEqual(p.a_dict()["costo_envio"], 6)
        p.distrito = "Los Olivos"
        p.peso = 2
        self.assertEqual(p.a_dict()["costo_envio"], 8)

    def test_totales_y_pendientes(self):
        pedidos = [Pedido("P001", 3, distrito="Surco"), Pedido("P002", 2, distrito="Independencia")]
        plan = planear_multi_viaje(pedidos)
        self.assertEqual(plan.a_dict()["costo_total"], 14)
        salida = Salida(1, detalle=[p.a_dict() for p in pedidos])
        pedidos[0].peso = 10
        self.assertEqual(Salida.desde_dict(salida.a_dict()).a_dict()["costo_total"], 14)
        plan = planear_multi_viaje([Pedido("P003", 2, distrito="Desconocido")])
        self.assertIsNone(plan.a_dict()["costo_total"])
        self.assertEqual(plan.a_dict()["costos_pendientes"], 1)
        self.assertIsNone(Salida(1, detalle=[{"peso": 2}]).a_dict()["costo_total"])

    def test_tarifas_editables_y_persistencia(self):
        import tempfile
        from pathlib import Path
        from nucleo.servicio import RAPPIDOS
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as carpeta:
            ruta = str(Path(carpeta) / "datos.json")
            servicio = RAPPIDOS(ruta)
            self.assertEqual(len(servicio.repositorio.tarifas), 10)
            pedido = servicio.registrar(3, distrito="Surco").datos
            salida = servicio.confirmar_carga(servicio.planear_carga().datos).datos
            self.assertTrue(servicio.guardar_tarifa(" SURCO ", "2,50").ok)
            self.assertEqual(pedido.a_dict()["costo_envio"], 7.5)
            self.assertEqual(salida.a_dict()["costo_total"], 6)
            self.assertTrue(servicio.guardar_tarifa("Ate", 5).ok)
            for valor in (0, -1, "NaN", "Infinity", "abc", "1.234"):
                self.assertFalse(servicio.guardar_tarifa("Surco", valor).ok)
            otro = RAPPIDOS(ruta)
            self.assertEqual(otro.repositorio.obtener(pedido.codigo).a_dict()["costo_envio"], 7.5)
            self.assertEqual(otro.repositorio.tarifas["Ate"], 5)
            self.assertEqual(otro.historial()[0].a_dict()["costo_total"], 6)
            self.assertEqual(RAPPIDOS(str(Path(carpeta) / "otro.json")).repositorio.tarifas["Surco"], 2)

    def test_distrito_nuevo_pendiente_y_cotizacion_posterior(self):
        import tempfile
        from pathlib import Path
        from nucleo.servicio import RAPPIDOS
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as carpeta:
            ruta = str(Path(carpeta) / "datos.json")
            servicio = RAPPIDOS(ruta)
            uno = servicio.registrar(2, distrito="Ate").datos
            dos = servicio.registrar(3, distrito=" ATE ").datos
            self.assertIn("Ate", servicio.repositorio.tarifas)
            self.assertEqual(len(servicio.repositorio.tarifas), 11)
            self.assertIsNone(uno.a_dict()["costo_envio"])
            self.assertIsNone(dos.a_dict()["costo_envio"])
            recargado = RAPPIDOS(ruta)
            self.assertIsNone(recargado.repositorio.tarifas["Ate"])
            self.assertTrue(servicio.guardar_tarifa("ate", 5).ok)
            self.assertEqual(uno.a_dict()["costo_envio"], 10)
            self.assertEqual(dos.a_dict()["costo_envio"], 15)
            servicio.editar(uno.codigo, distrito="Chaclacayo")
            self.assertIsNone(servicio.repositorio.tarifas["Chaclacayo"])
            self.assertIsNone(uno.a_dict()["costo_envio"])
            servicio.editar_masivo([uno.codigo, dos.codigo], distrito="Lurin")
            self.assertIsNone(servicio.repositorio.tarifas["Lurin"])
            vista = servicio.importar("pedidos.csv", b"Peso,Distrito\n1.5,Comas\n").datos
            self.assertNotIn("Comas", servicio.repositorio.tarifas)
            servicio.confirmar_importacion(vista)
            self.assertIsNone(servicio.repositorio.tarifas["Comas"])
            self.assertTrue(servicio.guardar_tarifa("Comas", 4).ok)
            self.assertEqual(vista.pedidos[0].a_dict()["costo_envio"], 6)
