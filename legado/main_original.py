#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modulo main_original."""

import os
from funciones import *

while True:

    print("\n       RAPPIDOS - SISTEMA DE PEDIDOS")
    print("1. Registrar pedido")
    print("2. Mostrar pedidos")
    print("3. Preparar Salida de Pedido")
    print("4. Pedido por prioridad ")
    print("5. Salir")

    opcion = input("Ingrese una opción: ")

    if opcion == "1":
        registrar_pedido()

    elif opcion == "2":
        mostrar_pedidos()

    elif opcion == "3":
        print("Preparar Pedido")
        preparar_salida()

    elif opcion == "4":
        print("Pedido por prioridad")
        pedido_prioridad()
        break

    elif opcion == "5":
        print("Saliendo del programa...")
        break

    else:
        print("Opción no válida")
        