"""
 nucleo.servicio
 ===============

 Fachada de casos de uso de RAPPIDOS. Esta es la clase que consume TANTO la
 version de consola como la version web.

 Por que una fachada y no llamar a los modulos internos directamente:

    - Un solo lugar donde vive la REGLA DE NEGOCIO. Si mañana el vehiculo
      pasa de 30 kg a 35 kg, se cambia en un archivo.
    - Las interfaces (consola, web) no dependen de los detalles internos,
      asi que un cambio en el algoritmo no rompe la interfaz.
    - Todas las funciones devuelven `ResultadoOperacion`, un tipo uniforme.
      La interfaz no necesita try/except disperso ni conocer el tipo de
      dato con el que responde cada caso de uso.

 Este es el patron Fachada (GoF). Es appropriate cuando se quiere encapsular
 un subsistema complejo detras de una interfaz sencilla.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from .algoritmos import (
    busqueda_binaria_codigo,
    busqueda_lineal_codigo,
    comparar_algoritmos,
    ordenar,
)
from .generador import GeneradorPedidos
from .importador import ResultadoImportacion, _a_float, importar_archivo
from .modelos import (
    CAPACIDAD_VEHICULO_KG,
    EstadoPedido,
    EstrategiaOrden,
    EstrategiaReparto,
    Pedido,
    PREFIJO_CODIGO,
    ResultadoOperacion,
    Salida,
    ahora,
)
from .reparto import ObjetivoMochila, PlanSalida, comparar_estrategias, planear_salida
from .repositorio import Repositorio


class RAPPIDOS:
    """Punto de entrada unico al sistema de pedidos."""

    def __init__(self, ruta_datos: Optional[str] = None, semilla: Optional[int] = None) -> None:
        self.repositorio = Repositorio(ruta_datos)
        self.generador = GeneradorPedidos(semilla)

    # ================================================================
    # CASOS DE USO: registro
    # ================================================================

    def registrar(
        self,
        peso: Any,
        direccion: str = "",
        cliente: str = "",
        telefono: str = "",
    ) -> ResultadoOperacion:
        """Registra un pedido individual.

        Acepta el peso como texto o como numero porque llega desde un
        formulario web (que lo manda como cadena) y desde la consola
        (donde el usuario lo teclea). La validacion se hace UNA sola vez
        aqui, en el nucleo, para que ninguna interfaz tenga que repetirla.
        """
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
    ) -> ResultadoOperacion:
        """Registra varios pedidos de una vez reutilizando la validacion.

        Se recorre la lista completa en vez de llamar a `registrar` en
        bucle, para no escribir el archivo 200 veces. Una sola escritura al
        final es la diferencia entre milisegundos y segundos con carga
        masiva, y es el motivo por el que esta funcion existe aparte.
        """
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

            if direcciones and indice < len(direcciones):
                direccion = str(direcciones[indice]).strip()

            pedido = Pedido(
                codigo=self.repositorio.avanzar_contador(),
                peso=valor,
                direccion=direccion,
                fecha_registro=ahora(),
            )
            self.repositorio.agregar(pedido)
            creados.append(pedido)

        self.repositorio.guardar()

        mensaje = f"{len(creados)} pedido(s) registrados."

        if errores:
            mensaje += f" {len(errores)} descartado(s) por peso invalido."

        return ResultadoOperacion.exito(mensaje, creados)

    def generar_masivo(
        self, cantidad: int, con_direcciones: bool = True, semilla: Optional[int] = None
    ) -> ResultadoOperacion:
        """Genera pedidos aleatorios con direcciones, para pruebas y metricas."""
        if cantidad <= 0:
            return ResultadoOperacion.error("La cantidad debe ser mayor que cero.")

        if cantidad > 5000:
            return ResultadoOperacion.error("Maximo 5000 pedidos por generacion.")

        if not con_direcciones:
            pesos = [self.generador.peso_aleatorio() for _ in range(cantidad)]
            return self.registrar_lote(pesos)

        if semilla is not None:
            self.generador = GeneradorPedidos(semilla)

        codigos = [f"{PREFIJO_CODIGO}{self.repositorio.contador + i:03d}" for i in range(cantidad)]
        pedidos = self.generador.generar(cantidad, codigos)

        for pedido in pedidos:
            pedido.fecha_registro = ahora()
            self.repositorio.agregar(pedido)
            self.repositorio.contador += 1

        self.repositorio.guardar()

        peso_total = round(sum(p.peso for p in pedidos), 2)
        return ResultadoOperacion.exito(
            f"{cantidad} pedidos generados con direcciones aleatorias ({peso_total} kg).",
            pedidos,
        )

    def importar(
        self, nombre_archivo: str, contenido: bytes
    ) -> ResultadoOperacion:
        """Carga masiva desde un archivo CSV, TXT o XLSX."""
        codigos = [
            f"{PREFIJO_CODIGO}{self.repositorio.contador + i:03d}"
            for i in range(6000)
        ]

        resultado: ResultadoImportacion = importar_archivo(
            nombre_archivo, contenido, codigos
        )

        if not resultado.pedidos:
            detalle = resultado.errores[0].mensaje if resultado.errores else "sin datos validos"
            return ResultadoOperacion.error(
                f"No se importo ningun pedido: {detalle}", resultado
            )

        for pedido in resultado.pedidos:
            pedido.fecha_registro = ahora()
            self.repositorio.agregar(pedido)
            self.repositorio.contador += 1

        self.repositorio.guardar()

        mensaje = resultado.resumen()

        if resultado.total_errores:
            mensaje += f" Primer error: fila {resultado.errores[0].linea}, {resultado.errores[0].mensaje}"

        return ResultadoOperacion.exito(mensaje, resultado)

    # ================================================================
    # CASOS DE USO: consulta
    # ================================================================

    def listar(
        self,
        peso_min: Optional[float] = None,
        peso_max: Optional[float] = None,
        solo_pendientes: bool = True,
        orden: Optional[EstrategiaOrden] = None,
        descendente: bool = False,
    ) -> List[Pedido]:
        """Lista pedidos con filtros de peso y ordenamiento opcional.

        El filtro se aplica ANTES de ordenar: filtrar despues obligaria a
        ordenar elementos que despues se descartan, que es trabajo perdido.
        """
        pedidos = self.repositorio.listar(solo_pendientes=solo_pendientes)

        if peso_min is not None:
            pedidos = [p for p in pedidos if p.peso >= peso_min]

        if peso_max is not None:
            pedidos = [p for p in pedidos if p.peso <= peso_max]

        if orden is not None:
            return ordenar(pedidos, lambda p: p.peso, orden, descendente).elementos

        return sorted(pedidos, key=lambda p: p.peso, reverse=descendente)

    def buscar(self, codigo: str, usar_binaria: bool = True) -> ResultadoOperacion:
        """Busca un pedido por codigo usando busqueda binaria o lineal.

        El metodo se elige segun el caso: la busqueda binaria es O(log n)
        pero EXIGE que la lista este ordenada, y el codigo se normaliza a
        mayusculas porque el usuario puede escribir "p001".
        """
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
        """Mide todos los algoritmos de ordenamiento sobre los pendientes.

        Si se indica una estrategia, devuelve ademas el detalle de como
        quedo el ordenamiento con ese algoritmo, para poder auditar el
        resultado y no solo el tiempo.
        """
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
        """Ejecuta la MISMA busqueda con ambos algoritmos y compara.

        Sirve para evidenciar la diferencia asintotica: la busqueda lineal
        recorre hasta n elementos y la binaria solo log2(n). Con pocos
        pedidos la diferencia es minima, y por eso hay que medirla con
        volumen.
        """
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

    # ================================================================
    # CASOS DE USO: salida
    # ================================================================

    def planear(
        self,
        estrategia: EstrategiaReparto = EstrategiaReparto.PRIMERO_QUE_CABE,
        prioritario: Optional[str] = None,
        objetivo: str = ObjetivoMochila.CANTIDAD,
        capacidad: float = CAPACIDAD_VEHICULO_KG,
    ) -> ResultadoOperacion:
        """Simula la salida SIN modificar el sistema.

        Devuelve un `PlanSalida` que la interfaz muestra para pedir
        confirmacion. Nada se borra hasta que se llame a `confirmar_salida`.
        """
        pendientes = self.repositorio.listar(solo_pendientes=True)

        if not pendientes:
            return ResultadoOperacion.error("No hay pedidos pendientes.")

        if prioritario:
            objetivo_pedido = prioritario.strip().upper()

            if not any(p.codigo == objetivo_pedido for p in pendientes):
                return ResultadoOperacion.error(
                    f"El pedido {objetivo_pedigo} no esta entre los pendientes."
                )

            prioritario = objetivo_pedido

        plan = planear_salida(pendientes, estrategia, capacidad, prioritario, objetivo)

        return ResultadoOperacion.exito(
            f"Plan generado: {plan.cantidad} pedido(s), {plan.peso_total} kg.", plan
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
        """Ejecuta el plan: marca los pedidos como despachados.

        A diferencia de la version original, los pedidos NO se eliminan del
        historial: pasan a estado DESPACHADO. Borrarlos hacia irrecoverable
        la trazabilidad, que es justamente lo que un sistema de reparto
        necesita para saber que entrego y cuando.
        """
        if not plan.seleccionados:
            return ResultadoOperacion.error("El plan no tiene pedidos para despachar.")

        momento = ahora()
        codigos = []

        for pedido in plan.seleccionados:
            pedido.estado = EstadoPedido.DESPACHADO
            pedido.fecha_despacho = momento
            codigos.append(pedido.codigo)

        salida = Salida(
            id=len(self.repositorio.salidas) + 1,
            codigos=codigos,
            peso_total=round(plan.peso_total, 2),
            capacidad=plan.capacidad,
            cantidad=plan.cantidad,
            estrategia=plan.estrategia.etiqueta,
            prioritario=plan.prioritario,
            fecha=momento,
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

    # ================================================================
    # CASOS DE USO: mantenimiento
    # ================================================================

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
        """Metricas del sistema para el panel de estadisticas.

        Incluye el histograma de pesos, que es lo que permite ver de un
        vistazo si la carga esta bien repartida o si se concentran pedidos
        muy pesados.
        """
        todos = self.repositorio.listar(solo_pendientes=False)
        pendientes = [p for p in todos if p.pendiente]
        despachados = [p for p in todos if not p.pendiente]
        salidas = self.repositorio.salidas

        peso_pendientes = sum(p.peso for p in pendientes)
        peso_despachados = sum(p.peso for p in despachados)

        viajes_necesarios = (
            (peso_pendientes / CAPACIDAD_VEHICULO_KG) if peso_pendientes else 0.0
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
                # `math.ceil` redondea hacia arriba: si hacen falta 60.2
                # viajes, hacen falta 61, porque un viaje parcial no
                # transporta pedidos. Truncar dejaria pedidos sin
                # entregar y sobraria capacidad en el ultimo viaje.
                "viajes_necesarios": math.ceil(viajes_necesarios),
                # El porcentaje de ocupacion se satura en 100: con reparto
                # optimo la ultima viaje suele ir casi vacia.
                "ocupacion_teorica": min(round(viajes_necesarios * 100, 1), 100.0),
            },
            "histograma": self._histograma(pendientes),
            "distribucion_zonas": self._distribucion_zonas(pendientes),
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
        """Agrupa los pesos en intervalos iguales.

        Se elige la cantidad de intervalos a partir del peso maximo, no de
        forma fija, para que el grafico sea legible tanto con 5 pedidos como
        con 2000.
        """
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

        return grupos

    def _distribucion_zonas(self, pedidos: Sequence[Pedido]) -> List[Dict[str, Any]]:
        """Cuenta pedidos por barrio, para saber donde se concentra la carga.

        La zona se toma de lo que sigue a la coma en la direccion, que es
        donde este generador coloca el barrio. Si el usuario escribio una
        direccion sin barrio, cae en "Sin zona".
        """
        conteo: Dict[str, int] = {}

        for pedido in pedidos:
            if "," in pedido.direccion:
                zona = pedido.direccion.rsplit(",", 1)[-1].strip()
            else:
                zona = "Sin zona"

            zona = zona or "Sin zona"
            conteo[zona] = conteo.get(zona, 0) + 1

        totales = sorted(conteo.items(), key=lambda par: par[1], reverse=True)

        return [{"zona": zona, "cantidad": cantidad} for zona, cantidad in totales[:8]]

    # ================================================================
    # Utilidad interna
    # ================================================================

    @staticmethod
    def _a_peso(peso: Any) -> float:
        """Normaliza a peso en kg con dos decimales.

        Delega en `_a_float` para que la consola y el importador de
        archivos acepten exactamente los mismos formatos numericos.
        """
        return round(float(_a_float(peso)), 2)

    @staticmethod
    def _validar_peso(peso: Any) -> str:
        """Valida el peso en el nucleo. Devuelve el error o cadena vacia.

        Vive aqui, y no en la interfaz, a proposito: es una regla del
        dominio, no una presentacion. Si se validara en el formulario, la
        consola podria aceptar pedidos que la web rechaza.
        """
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
