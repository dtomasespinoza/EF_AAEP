"""Regresiones del CSV con encabezados KILO y NUMERO. Sin dependencias extra."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nucleo.importador import importar_archivo


class PruebaEncabezados(unittest.TestCase):
    def test_csv_del_usuario(self):
        contenido = (
            "KILO,DISTRITO,DIRECCION,CLIENTE,NUMERO\n"
            "2.50,Miraflores,Calle Porta 245,Ana García,900123451\n"
            "17.90,San Martín de Porres,Avenida Perú 2850,Ricardo Vega,900123470\n"
        ).encode("utf-8-sig")
        resultado = importar_archivo("pedidos.csv", contenido, ["P009", "P010"])
        self.assertEqual(resultado.total_errores, 0)
        self.assertEqual(resultado.total_importados, 2)
        primero = resultado.pedidos[0]
        self.assertEqual(primero.peso, 2.5)
        self.assertEqual(primero.distrito, "Miraflores")
        self.assertEqual(primero.direccion, "Calle Porta 245")
        self.assertEqual(primero.cliente, "Ana García")
        self.assertEqual(primero.telefono, "900123451")
        self.assertEqual(resultado.pedidos[1].distrito, "San Martín de Porres")
        self.assertEqual(resultado.pedidos[1].telefono, "900123470")

    def test_txt_con_columnas_reordenadas(self):
        contenido = (
            "Direccion;Numero;Distrito;Kilos;Cliente\n"
            "Calle Porta 245;900123451;Miraflores;2,50;Ana García\n"
        ).encode("utf-8")
        resultado = importar_archivo("pedidos.txt", contenido, ["P001"])
        self.assertEqual(resultado.total_errores, 0)
        self.assertEqual(resultado.pedidos[0].peso, 2.5)
        self.assertEqual(resultado.pedidos[0].telefono, "900123451")

    def test_encabezado_sin_peso_no_recurre_a_posiciones(self):
        contenido = b"Direccion,Distrito,Cliente,Numero\n2.50,Miraflores,Ana,900123451\n"
        resultado = importar_archivo("pedidos.csv", contenido, [])
        self.assertEqual(resultado.total_importados, 0)
        self.assertIn("columna de peso", resultado.errores[0].mensaje)


if __name__ == "__main__":
    unittest.main()
