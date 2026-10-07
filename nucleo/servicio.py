"""Operaciones del sistema de pedidos."""

from __future__ import annotations

import math
from .costos import normalizar
from typing import Any, Dict, List, Optional, Sequence

from .algoritmos import (
    busqueda_binaria_codigo,
    busqueda_lineal_codigo,
    comparar_algoritmos,
    ordenar,
)
from .importador import ResultadoImportacion, _a_float, importar_archivo
from .modelos import (
    CAPACIDAD_VEHICULO_KG,
    CampoOrden,
    EstadoPedido,
    EstrategiaOrden,
    EstrategiaReparto,
    Pedido,
    PREFIJO_CODIGO,
    ResultadoOperacion,
    Salida,
    ahora,
)
from .reparto import (
    ObjetivoMochila,
    PlanCarga,
    PlanSalida,
    comparar_estrategias,
    planear_multi_viaje,
    planear_salida,
    planear_viajes,
)
from .repositorio import Repositorio

class RAPPIDOS:
    """Punto de entrada unico al sistema de pedidos."""

    def __init__(self, ruta_datos: Optional[str] = None) -> None:
        self.repositorio = Repositorio(ruta_datos)

    def guardar_tarifa(self, distrito: str, tarifa: Any) -> ResultadoOperacion:
        nombre = " ".join(str(distrito or "").split())
        if not nombre:
            return ResultadoOperacion.error("Ingrese un distrito.")
        if normalizar(nombre) == "santiago de surco":
            nombre = "Surco"
        try:
            from decimal import Decimal, InvalidOperation
            valor = Decimal(str(tarifa).replace(",", "."))
            if not valor.is_finite() or valor <= 0 or valor != valor.quantize(Decimal("0.01")):
                return ResultadoOperacion.error("La tarifa debe ser positiva y tener como maximo dos decimales.")
        except (InvalidOperation, ValueError, TypeError):
            return ResultadoOperacion.error("Ingrese una tarifa valida en soles por kg.")
        tarifas = self.repositorio.tarifas
        clave = next((d for d in tarifas if normalizar(d) == normalizar(nombre)), nombre)
        anterior = dict(tarifas)
        tarifas[clave] = float(valor)
        try:
            self.repositorio.guardar()
        except OSError:
            tarifas.clear()
            tarifas.update(anterior)
            return ResultadoOperacion.error("No se pudo guardar la tarifa. Intente nuevamente.")
        return ResultadoOperacion.exito("Tarifa guardada.")

    def registrar(
        self,
        peso: Any,
        direccion: str = "",
        cliente: str = "",
        telefono: str = "",
        distrito: str = "",
    ) -> ResultadoOperacion:
        """Registra un pedido individual."""
        error = self._validar_peso(peso)

        if error:
            return ResultadoOperacion.error(error)

        valor = self._a_peso(peso)
        codigo = self.repositorio.avanzar_contador()

        pedido = Pedido(
            codigo=codigo,
            peso=valor,
            direccion=direccion.strip(),
            cliente=cliente.strip(),
            telefono=telefono.strip(),
            distrito=distrito.strip(),
            fecha_registro=ahora(),
        )

        self.repositorio.agregar(pedido)
        self.repositorio.guardar()

        return ResultadoOperacion.exito(
            f"Pedido {codigo} registrado ({valor} kg).", pedido
        )

    def registrar_lote(
        self,
        pesos: Sequence[Any],
        direcciones: Optional[Sequence[str]] = None,
        distritos: Optional[Sequence[str]] = None,
    ) -> ResultadoOperacion:
        """Registra varios pedidos de una vez reutilizando la validacion."""
        if not pesos:
            return ResultadoOperacion.error("No hay pesos para registrar.")

        errores: List[str] = []
        creados: List[Pedido] = []

        for indice, peso in enumerate(pesos):
            error = self._validar_peso(peso)

            if error:
                errores.append(f"[{indice + 1}] {error}")
                continue

            valor = self._a_peso(peso)
            direccion = ""
            distrito = ""

            if direcciones and indice < len(direcciones):
                direccion = str(direcciones[indice]).strip()

            if distritos and indice < len(distritos):
                distrito = str(distritos[indice]).strip()

            pedido = Pedido(
                codigo=self.repositorio.avanzar_contador(),
                peso=valor,
                direccion=direccion,
                distrito=distrito,
                fecha_registro=ahora(),
            )
            self.repositorio.agregar(pedido)
            creados.append(pedido)

        self.repositorio.guardar()

        mensaje = f"{len(creados)} pedido(s) registrados."

        if errores:
            mensaje += f" {len(errores)} descartado(s) por peso invalido."

        return ResultadoOperacion.exito(mensaje, creados)

    def editar(
        self,
        codigo: str,
        peso: Any = None,
        direccion: Optional[str] = None,
        cliente: Optional[str] = None,
        telefono: Optional[str] = None,
        distrito: Optional[str] = None,
    ) -> ResultadoOperacion:
        """Corrige un pedido ya registrado."""
        objetivo = codigo.strip().upper()
        pedido = self.repositorio.obtener(objetivo)

        if pedido is None:
            return ResultadoOperacion.error(f"No existe el pedido {objetivo}.")

        if peso is not None:
            error = self._validar_peso(peso)

            if error:
                return ResultadoOperacion.error(error)

            pedido.peso = self._a_peso(peso)

        if direccion is not None:
            pedido.direccion = direccion.strip()

        if cliente is not None:
            pedido.cliente = cliente.strip()

        if telefono is not None:
            pedido.telefono = telefono.strip()

        if distrito is not None:
            pedido.distrito = distrito.strip()

        self.repositorio.guardar()

        return ResultadoOperacion.exito(
            f"Pedido {pedido.codigo} actualizado ({pedido.peso} kg).", pedido
        )

    def editar_masivo(
        self,
        codigos: Sequence[str],
        peso: Any = None,
        distrito: Optional[str] = None,
        cliente: Optional[str] = None,
    ) -> ResultadoOperacion:
        """Aplica la misma correccion a varios pedidos de una vez."""
        if not codigos:
            return ResultadoOperacion.error("No se selecciono ningun pedido.")

        peso_final = None

        if peso is not None:
            error = self._validar_peso(peso)

            if error:
                return ResultadoOperacion.error(error)

            peso_final = self._a_peso(peso)

        existentes = []

        for codigo in codigos:
            pedido = self.repositorio.obtener(codigo)

            if pedido is not None:
                existentes.append(pedido)

        if not existentes:
            return ResultadoOperacion.error("Ninguno de los codigos existe.")

        for pedido in existentes:
            if peso_final is not None:
                pedido.peso = peso_final

            if distrito is not None:
                pedido.distrito = distrito.strip()

            if cliente is not None:
                pedido.cliente = cliente.strip()

        self.repositorio.guardar()

        return ResultadoOperacion.exito(
            f"{len(existentes)} pedido(s) actualizados.", existentes
        )

    def importar(
        self, nombre_archivo: str, contenido: bytes
    ) -> ResultadoOperacion:
        """Analiza un archivo CSV, TXT o XLSX SIN registrar nada."""
        codigos = [
            f"{PREFIJO_CODIGO}{self.repositorio.contador + i:03d}"
            for i in range(6000)
        ]

        resultado: ResultadoImportacion = importar_archivo(
            nombre_archivo, contenido, codigos
        )

        for pedido in resultado.pedidos:
            pedido.tarifas = self.repositorio.tarifas

        if not resultado.pedidos:
            detalle = resultado.errores[0].mensaje if resultado.errores else "sin datos validos"
            return ResultadoOperacion.error(
                f"No se importo ningun pedido: {detalle}", resultado
            )

        mensaje = resultado.resumen()

        if resultado.total_errores:
            mensaje += f" Primer error: fila {resultado.errores[0].linea}, {resultado.errores[0].mensaje}"

        mensaje += " Confirme la importacion para guardarlos."

        return ResultadoOperacion.exito(mensaje, resultado)

    def confirmar_importacion(self, resultado: ResultadoImportacion) -> ResultadoOperacion:
        """Registra de verdad los pedidos de una vista previa ya revisada."""
        if resultado is None or not resultado.pedidos:
            return ResultadoOperacion.error("No hay pedidos para confirmar.")

        for pedido in resultado.pedidos:
            pedido.fecha_registro = ahora()
            self.repositorio.agregar(pedido)
            self.repositorio.contador += 1

        self.repositorio.guardar()

        mensaje = resultado.resumen()

        return ResultadoOperacion.exito(mensaje, resultado)

    def listar(
        self,
        peso_min: Optional[float] = None,
        peso_max: Optional[float] = None,
        solo_pendientes: bool = True,
        orden: Optional[EstrategiaOrden] = None,
        descendente: bool = False,
        campo: CampoOrden = CampoOrden.PESO,
        distrito: Optional[str] = None,
    ) -> List[Pedido]:
        """Lista pedidos con filtros de peso y distrito, y orden opcional."""
        pedidos = self.repositorio.listar(solo_pendientes=solo_pendientes)

        if peso_min is not None:
            pedidos = [p for p in pedidos if p.peso >= peso_min]

        if peso_max is not None:
            pedidos = [p for p in pedidos if p.peso <= peso_max]

        if distrito:
            objetivo = self._normalizar(distrito)
            pedidos = [p for p in pedidos if self._normalizar(p.distrito_efectivo) == objetivo]

        if not campo.admite_algoritmo:
            clave = self._clave_orden(campo)
            return sorted(pedidos, key=clave, reverse=descendente)

        if orden is not None:
            return ordenar(pedidos, lambda p: p.peso, orden, descendente).elementos

        return sorted(pedidos, key=lambda p: p.peso, reverse=descendente)

    @staticmethod
    def _clave_orden(campo: CampoOrden):
        """Devuelve la funcion `key` para ordenar por el campo pedido."""
        if campo is CampoOrden.CODIGO:
            return lambda pedido: pedido.codigo

        if campo is CampoOrden.DISTRITO:
            return lambda pedido: (
                RAPPIDOS._normalizar(pedido.distrito_efectivo),
                pedido.codigo,
            )

        return lambda pedido: pedido.peso

    @staticmethod
    def _normalizar(texto: str) -> str:
        """Minusculas, sin acentos y sin espacios sobrantes."""
        limpio = str(texto or "").strip().lower()

        for acento, base in (
            ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"),
            ("ú", "u"), ("ü", "u"), ("ñ", "n"),
        ):
            limpio = limpio.replace(acento, base)

        return limpio.strip()

    def buscar(self, codigo: str, usar_binaria: bool = True) -> ResultadoOperacion:
        """Busca un pedido por codigo usando busqueda binaria o lineal."""
        if not codigo or not codigo.strip():
            return ResultadoOperacion.error("Ingrese un codigo de pedido.")

        objetivo = codigo.strip().upper()
        pendientes = self.repositorio.listar(solo_pendientes=False)

        if not pendientes:
            return ResultadoOperacion.error("No hay pedidos registrados.")

        if usar_binaria:
            resultado = busqueda_binaria_codigo(pendientes, objetivo)
        else:
            resultado = busqueda_lineal_codigo(pendientes, objetivo)

        if not resultado.encontrado:
            return ResultadoOperacion.error(
                f"No se encontro el pedido {objetivo}.", resultado
            )

        return ResultadoOperacion.exito(
            f"Pedido {objetivo} encontrado en {resultado.comparaciones} comparaciones.",
            {"pedido": resultado.elemento, "busqueda": resultado.a_dict()},
        )

    def comparar_algoritmos(
        self, estrategia: Optional[EstrategiaOrden] = None, descendente: bool = False
    ) -> ResultadoOperacion:
        """Mide todos los algoritmos de ordenamiento sobre los pendientes."""
        pedidos = self.repositorio.listar(solo_pendientes=True)

        if not pedidos:
            return ResultadoOperacion.error("No hay pedidos pendientes para ordenar.")

        metricas = comparar_algoritmos(pedidos, lambda p: p.peso, descendente)
        datos: Dict[str, Any] = {"metricas": [m.a_dict() for m in metricas]}

        if estrategia is not None:
            resultado = ordenar(pedidos, lambda p: p.peso, estrategia, descendente)
            datos["detalle"] = {
                "algoritmo": resultado.metrica.nombre,
                "pedidos": [p.a_dict() for p in resultado.elementos],
            }

        return ResultadoOperacion.exito(
            f"{len(pedidos)} pedidos medidos con {len(metricas)} algoritmos.", datos
        )

    def buscar_codigo_por_algoritmo(self, codigo: str) -> ResultadoOperacion:
        """Ejecuta la MISMA busqueda con ambos algoritmos y compara."""
        pendientes = self.repositorio.listar(solo_pendientes=False)

        if not pendientes:
            return ResultadoOperacion.error("No hay pedidos registrados.")

        objetivo = codigo.strip().upper()
        lineal = busqueda_lineal_codigo(pendientes, objetivo)
        binaria = busqueda_binaria_codigo(pendientes, objetivo)

        return ResultadoOperacion.exito(
            f"Busqueda de {objetivo} en {len(pendientes)} pedidos.", {
                "lineal": lineal.a_dict(),
                "binaria": binaria.a_dict(),
                "ahorro": lineal.comparaciones - binaria.comparaciones,
            }
        )

    def planear(
        self,
        estrategia: EstrategiaReparto = EstrategiaReparto.PRIMERO_QUE_CABE,
        prioritario: Optional[str] = None,
        objetivo: str = ObjetivoMochila.CANTIDAD,
        capacidad: float = CAPACIDAD_VEHICULO_KG,
    ) -> ResultadoOperacion:
        """Simula la salida de UN viaje SIN modificar el sistema."""
        pendientes = self.repositorio.listar(solo_pendientes=True)

        if not pendientes:
            return ResultadoOperacion.error("No hay pedidos pendientes.")

        if prioritario:
            objetivo_pedido = prioritario.strip().upper()

            if not any(p.codigo == objetivo_pedido for p in pendientes):
                return ResultadoOperacion.error(
                    f"El pedido {objetivo_pedido} no esta entre los pendientes."
                )

            prioritario = objetivo_pedido

        plan = planear_salida(pendientes, estrategia, capacidad, prioritario, objetivo)

        return ResultadoOperacion.exito(
            f"Plan generado: {plan.cantidad} pedido(s), {plan.peso_total} kg.", plan
        )

    def planear_carga(
        self,
        viajes: int = 0,
        estrategia: EstrategiaReparto = EstrategiaReparto.MOCHILA_0_1,
        prioritario: Optional[str] = None,
        objetivo: str = ObjetivoMochila.CANTIDAD,
        capacidad: float = CAPACIDAD_VEHICULO_KG,
    ) -> ResultadoOperacion:
        """Simula el reparto completo en uno o varios viajes."""
        pendientes = self.repositorio.listar(solo_pendientes=True)

        if not pendientes:
            return ResultadoOperacion.error("No hay pedidos pendientes.")

        if prioritario:
            objetivo_pedido = prioritario.strip().upper()

            if not any(p.codigo == objetivo_pedido for p in pendientes):
                return ResultadoOperacion.error(
                    f"El pedido {objetivo_pedido} no esta entre los pendientes."
                )

            prioritario = objetivo_pedido

        if viajes and viajes > 1:
            plan = planear_viajes(
                pendientes, viajes, estrategia, capacidad, prioritario, objetivo
            )
        elif viajes == 1:
            plan = planear_viajes(
                pendientes, 1, estrategia, capacidad, prioritario, objetivo
            )
        else:
            plan = planear_multi_viaje(
                pendientes, estrategia, capacidad, prioritario, objetivo
            )

        if not plan.viajes:
            return ResultadoOperacion.error(
                "Ningun pedido cabe en la capacidad del vehiculo."
            )

        mensaje = (
            f"{len(plan.viajes)} viaje(s) preparado(s): "
            f"{plan.total_pedidos} pedido(s), {plan.peso_total} kg."
        )

        if plan.no_asignados:
            mensaje += f" {len(plan.no_asignados)} pedido(s) quedan fuera."

        return ResultadoOperacion.exito(mensaje, plan)

    def confirmar_carga(self, plan: PlanCarga) -> ResultadoOperacion:
        """Despacha TODOS los viajes de un plan multi-viaje de una vez."""
        if plan is None or not plan.viajes:
            return ResultadoOperacion.error("El plan no tiene viajes para despachar.")

        total = sum(viaje.cantidad for viaje in plan.viajes)

        if total == 0:
            return ResultadoOperacion.error("El plan no tiene pedidos para despachar.")

        momento = ahora()
        detalle: List[Dict[str, Any]] = []
        codigos: List[str] = []

        for viaje in plan.viajes:
            for pedido in viaje.pedidos:
                pedido.estado = EstadoPedido.DESPACHADO
                pedido.fecha_despacho = momento
                codigos.append(pedido.codigo)
                detalle.append(
                    {
                        **{k: pedido.a_dict()[k] for k in ("tarifa_kg", "costo_envio")},
                        "codigo": pedido.codigo,
                        "peso": pedido.peso,
                        "distrito": pedido.distrito_efectivo,
                        "direccion": pedido.direccion,
                        "cliente": pedido.cliente,
                        "telefono": pedido.telefono,
                        "viaje": viaje.numero,
                    }
                )

        peso_total = round(sum(p["peso"] for p in detalle), 2)

        salida = Salida(
            id=len(self.repositorio.salidas) + 1,
            codigos=codigos,
            peso_total=peso_total,
            capacidad=plan.capacidad,
            cantidad=total,
            estrategia=plan.estrategia.etiqueta if plan.estrategia else "",
            fecha=momento,
            detalle=detalle,
            viajes=len(plan.viajes),
        )

        self.repositorio.registrar_salida(salida)
        self.repositorio.guardar()

        return ResultadoOperacion.exito(
            f"{len(plan.viajes)} viaje(s) despachado(s): {total} pedido(s), "
            f"{salida.peso_total} kg entregados.",
            salida,
        )

    def comparar_estrategias(self, prioritario: Optional[str] = None) -> ResultadoOperacion:
        """Compara las tres estrategias sobre los mismos pedidos."""
        pendientes = self.repositorio.listar(solo_pendientes=True)

        if not pendientes:
            return ResultadoOperacion.error("No hay pedidos pendientes.")

        planes = comparar_estrategias(pendientes, prioritario=prioritario)
        mejor = max(planes, key=lambda p: (p.cantidad, p.peso_total))

        return ResultadoOperacion.exito(
            f"La mejor estrategia es: {mejor.estrategia.etiqueta} con {mejor.cantidad} pedido(s).",
            {"planes": [p.a_dict() for p in planes], "mejor": mejor.estrategia.value},
        )

    def confirmar_salida(self, plan: PlanSalida) -> ResultadoOperacion:
        """Ejecuta el plan: marca los pedidos como despachados."""
        if not plan.seleccionados:
            return ResultadoOperacion.error("El plan no tiene pedidos para despachar.")

        momento = ahora()
        codigos = []
        detalle: List[Dict[str, Any]] = []

        for pedido in plan.seleccionados:
            pedido.estado = EstadoPedido.DESPACHADO
            pedido.fecha_despacho = momento
            codigos.append(pedido.codigo)
            detalle.append(
                {
                    **{k: pedido.a_dict()[k] for k in ("tarifa_kg", "costo_envio")},
                    "codigo": pedido.codigo,
                    "peso": pedido.peso,
                    "distrito": pedido.distrito_efectivo,
                    "direccion": pedido.direccion,
                    "cliente": pedido.cliente,
                    "telefono": pedido.telefono,
                    "viaje": 1,
                }
            )

        salida = Salida(
            id=len(self.repositorio.salidas) + 1,
            codigos=codigos,
            peso_total=round(plan.peso_total, 2),
            capacidad=plan.capacidad,
            cantidad=plan.cantidad,
            estrategia=plan.estrategia.etiqueta,
            prioritario=plan.prioritario,
            fecha=momento,
            detalle=detalle,
        )

        self.repositorio.registrar_salida(salida)
        self.repositorio.guardar()

        return ResultadoOperacion.exito(
            f"Salida #{salida.id} confirmada: {plan.cantidad} pedido(s), "
            f"{salida.peso_total} kg entregados.",
            salida,
        )

    def historial(self, limite: int = 50) -> List[Salida]:
        """Ultimas salidas registradas, de la mas reciente a la mas antigua."""
        return list(reversed(self.repositorio.salidas[-limite:]))

    def detalle_salida(self, identificador: int) -> ResultadoOperacion:
        """Devuelve una salida concreta con el detalle de lo que llevo."""
        for salida in self.repositorio.salidas:
            if salida.id == identificador:
                return ResultadoOperacion.exito(
                    f"Salida #{salida.id}: {salida.cantidad} pedido(s).",
                    salida.a_dict(),
                )

        return ResultadoOperacion.error(f"No existe la salida #{identificador}.")

    def devolver_a_pendientes(self, codigo: str) -> ResultadoOperacion:
        """Reabre un pedido despachado. Permite corregir errores de operacion."""
        pedido = self.repositorio.obtener(codigo.strip().upper())

        if pedido is None:
            return ResultadoOperacion.error(f"No existe el pedido {codigo}.")

        if pedido.pendiente:
            return ResultadoOperacion.error(f"El pedido {pedido.codigo} ya esta pendiente.")

        pedido.estado = EstadoPedido.PENDIENTE
        pedido.fecha_despacho = ""
        self.repositorio.guardar()

        return ResultadoOperacion.exito(f"Pedido {pedido.codigo} devuelto a pendientes.", pedido)

    def eliminar(self, codigo: str) -> ResultadoOperacion:
        """Elimina un pedido de forma definitiva."""
        codigo = codigo.strip().upper()

        if self.repositorio.obtener(codigo) is None:
            return ResultadoOperacion.error(f"No existe el pedido {codigo}.")

        self.repositorio.eliminar(codigo)
        self.repositorio.guardar()

        return ResultadoOperacion.exito(f"Pedido {codigo} eliminado.")

    def limpiar(self, solo_pendientes: bool = True) -> ResultadoOperacion:
        """Vacia pedidos pendientes o borra absolutamente todo."""
        if solo_pendientes:
            cantidad = self.repositorio.vaciar_pendientes()
            self.repositorio.guardar()
            return ResultadoOperacion.exito(f"{cantidad} pedido(s) pendiente(s) eliminado(s).")

        self.repositorio.limpiar_todo()
        self.repositorio.guardar()
        return ResultadoOperacion.exito("Todos los datos fueron eliminados.")

    def estadisticas(self) -> ResultadoOperacion:
        """Metricas del sistema para el panel de estadisticas."""
        todos = self.repositorio.listar(solo_pendientes=False)
        pendientes = [p for p in todos if p.pendiente]
        despachados = [p for p in todos if not p.pendiente]
        salidas = self.repositorio.salidas

        peso_pendientes = sum(p.peso for p in pendientes)
        peso_despachados = sum(p.peso for p in despachados)

        pesos_distrito = {}
        sin_distrito = 0
        for pedido in pendientes:
            distrito = self._normalizar(pedido.distrito_efectivo)
            if distrito:
                pesos_distrito[distrito] = pesos_distrito.get(distrito, 0) + pedido.peso
            else:
                sin_distrito += 1
        viajes_necesarios = sin_distrito + sum(
            math.ceil(round(peso, 2) / CAPACIDAD_VEHICULO_KG)
            for peso in pesos_distrito.values()
        )
        ocupacion = (
            peso_pendientes / (viajes_necesarios * CAPACIDAD_VEHICULO_KG) * 100
            if viajes_necesarios else 0
        )

        return ResultadoOperacion.exito("Estadisticas calculadas.", {
            "resumen": {
                "total_pedidos": len(todos),
                "pendientes": len(pendientes),
                "despachados": len(despachados),
                "peso_pendientes": round(peso_pendientes, 2),
                "peso_despachados": round(peso_despachados, 2),
                "peso_promedio": round(peso_pendientes / len(pendientes), 2) if pendientes else 0.0,
                "peso_maximo": max((p.peso for p in pendientes), default=0.0),
                "peso_minimo": min((p.peso for p in pendientes), default=0.0),
                "capacidad": CAPACIDAD_VEHICULO_KG,

                "viajes_necesarios": math.ceil(viajes_necesarios),

                "ocupacion_teorica": min(round(ocupacion, 1), 100.0),
            },
            "histograma": self._histograma(pendientes),
            "distribucion_distritos": self._distribucion_distritos(pendientes),
            "distritos": sorted(
                {
                    self._normalizar(p.distrito_efectivo) or "sin distrito"
                    for p in pendientes
                }
            ),
            "salidas": [
                {
                    "id": salida.id,
                    "fecha": salida.fecha,
                    "cantidad": salida.cantidad,
                    "peso_total": salida.peso_total,
                    "ocupacion": round(salida.peso_total / salida.capacidad * 100, 1) if salida.capacidad else 0.0,
                    "estrategia": salida.estrategia,
                }
                for salida in reversed(salidas[-10:])
            ],
            "almacen": self.repositorio.estadisticas_almacen(),
        })

    def _histograma(self, pedidos: Sequence[Pedido], intervalos: int = 6) -> List[Dict[str, Any]]:
        """Agrupa los pesos en intervalos iguales."""
        if not pedidos:
            return []

        pesos = [p.peso for p in pedidos]
        menor = min(pesos)
        mayor = max(pesos)

        if mayor - menor < 0.01:
            return [{
                "etiqueta": f"{menor:g} kg",
                "rango": f"{menor:g} - {menor:g} kg",
                "cantidad": len(pesos),
            }]

        paso = (mayor - menor) / intervalos
        grupos = [{"etiqueta": "", "rango": "", "cantidad": 0} for _ in range(intervalos)]

        for peso in pesos:
            posicion = int((peso - menor) / paso)
            grupos[min(posicion, intervalos - 1)]["cantidad"] += 1

        for indice, grupo in enumerate(grupos):
            inicio = menor + indice * paso
            fin = inicio + paso
            grupo["etiqueta"] = f"{inicio:.1f}"
            grupo["rango"] = f"{inicio:.1f} - {fin:.1f} kg"

            pesos_tramo = [p for p in pedidos if p.peso >= inicio and p.peso < fin]
            if indice == intervalos - 1:
                pesos_tramo = [p for p in pedidos if p.peso >= inicio and p.peso <= mayor]
            grupo["peso"] = round(sum(p.peso for p in pesos_tramo), 2)

        return grupos

    def _distribucion_distritos(self, pedidos: Sequence[Pedido]) -> List[Dict[str, Any]]:
        """Cuenta pedidos y kilos por distrito."""
        conteo: Dict[str, Dict[str, Any]] = {}

        for pedido in pedidos:
            nombre = pedido.distrito_efectivo.strip() or "Sin distrito"
            clave = self._normalizar(nombre)

            if clave not in conteo:
                conteo[clave] = {"distrito": nombre, "cantidad": 0, "peso": 0.0}

            conteo[clave]["cantidad"] += 1
            conteo[clave]["peso"] += pedido.peso

        totales = sorted(
            conteo.values(), key=lambda par: (-par["cantidad"], par["distrito"])
        )

        for grupo in totales:
            grupo["peso"] = round(grupo["peso"], 2)

        return totales[:10]

    @staticmethod
    def _a_peso(peso: Any) -> float:
        """Normaliza a peso en kg con dos decimales."""
        return round(float(_a_float(peso)), 2)

    @staticmethod
    def _validar_peso(peso: Any) -> str:
        """Valida el peso en el nucleo. Devuelve el error o cadena vacia."""
        if peso is None or str(peso).strip() == "":
            return "Debe ingresar el peso del pedido."

        try:
            valor = float(_a_float(peso))
        except (ValueError, TypeError):
            return "El peso debe ser un numero."

        if valor <= 0:
            return "El peso debe ser mayor a 0 kg."

        if valor > CAPACIDAD_VEHICULO_KG:
            return f"El peso debe ser menor o igual a {CAPACIDAD_VEHICULO_KG:g} kg."

        return ""
