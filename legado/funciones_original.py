#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 21:31:31 2026

@author: jeremy
"""

import os



pedidos = {}
contador = 1

def registrar_pedido():
    global contador

    peso = float(input("Ingrese el peso del pedido en kg: "))

    if peso <= 0:
        print("El peso debe ser mayor a 0 kg.")
        
    elif peso > 30:
        print("El peso debe de ser menor a 30 kg")
    else:
        codigo = f"P{contador:03d}"

        pedidos[codigo] = {
            "peso": peso
        }

        print("Pedido registrado:", codigo)

        contador += 1    

def mostrar_pedidos():
    if not pedidos:
        print("No hay pedidos pendientes.")
    else:
        print("\n- PEDIDOS PENDIENTES -")

        for codigo, datos in pedidos.items():
            print("Código:", codigo)
            print("Peso:", datos["peso"], "kg")
            print("-------------------------")
    return        
            
    
    
def preparar_salida(cod_pri = None):
    if not pedidos:
        print("No hay pedidos pendientes.")
        return

    capacidad = 30
    peso_actual = 0
    pedidos_salida = {}
    
    if cod_pri is not None:
        peso_prio = pedidos[cod_pri]["peso"]
        
        pedidos_salida[cod_pri] = (pedidos[cod_pri])
        peso_actual += peso_prio
        
        print("\n Pedido prioritario")
        print(cod_pri, " - ", peso_prio, "kg")     

    pedidos_ordenados = ordenar_por_peso_burbuja(pedidos)

    for codigo, datos in pedidos_ordenados:
        
        if codigo == cod_pri:
            continue
                
        peso = datos["peso"]

        if peso_actual + peso <= capacidad:
            pedidos_salida[codigo] = datos
            peso_actual += peso

    print("\n--- PREPARAR SALIDA DE PEDIDOS ---")
    print("Pedidos seleccionados:")

    for codigo, datos in pedidos_salida.items():
        print(codigo, "-", datos["peso"], "kg")

    print("-------------------------")
    print("Peso total:", peso_actual, "kg")
    print("Capacidad:", capacidad, "kg")
    print("Peso disponible:", capacidad - peso_actual, "kg")

    confirmacion = input("\n¿Está seguro de preparar estos pedidos? (si/no): ")

    if confirmacion.lower() == "si":
        for codigo in pedidos_salida:
            del pedidos[codigo]

        print("Pedidos preparados correctamente.")

    else:
        print("La salida de pedidos fue cancelada.")    
    

def busqueda_codigo(pedidos, codigo):
    codigos = list(pedidos.keys())
    
    inicio = 0
    fin =len(codigos) - 1
    
    while inicio <= fin:
        mitad = (inicio + fin )//2
        
        if codigos[mitad] == codigo:
            return codigos[mitad]
        
        elif codigos[mitad] < codigo:
            inicio = mitad + 1
            
        else:
            fin = mitad - 1 
            
    return None
    
def pedido_prioridad():
    if pedidos == {}:
        print("No hay pedidos registrados")
        return
    
    codigo = input("Ingrese el código del pedido prioritario").upper()
    
    bus_cod = busqueda_codigo(pedidos, codigo)
    
    if bus_cod is not None:
        
        print("\n Pedido encontrado")
        print("Código de pedido prioritario: ", bus_cod)
        print("Peso ", pedidos[bus_cod]["peso"],"kg")
        print("Preparando salida prioritaria")
        preparar_salida(bus_cod)
    else:
        print("\n No se encontró el pedido")
        
    
def ordenar_por_peso_burbuja(pedidos):
    pedidos_ordenados = list(pedidos.items())

    for i in range(len(pedidos_ordenados)):
        for j in range(0, len(pedidos_ordenados) - i - 1):

            peso_actual = pedidos_ordenados[j][1]["peso"]
            peso_siguiente = pedidos_ordenados[j + 1][1]["peso"]

            if peso_actual > peso_siguiente:
                pedidos_ordenados[j], pedidos_ordenados[j + 1] = (
                    pedidos_ordenados[j + 1],
                    pedidos_ordenados[j]
                )

    return pedidos_ordenados    


def limpiar_consola():
    os.system("cls" if os.name == "nt" else "clear")
