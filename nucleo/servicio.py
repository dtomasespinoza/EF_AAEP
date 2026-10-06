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

    # ================================================================
    # CASOS DE USO: registro
    # ================================================================

    def registrar(
        self,
        peso: Any,
        direccion: str = "",
        cliente: str = "",
        telefono: str = "",
        distrito: str = "",
    ) -> ResultadoOperacion:
        """Registra un pedido individual.

        Acepta el peso como texto o como numero porque llega desde un
        formulario web (que lo manda como cadena) y desde la consola
        (donde el usuario lo teclea). La validacion se hace UNA sola vez
        aqui, en el nucleo, para que ninguna interfaz tenga que repetirla.

        `distrito` va APARTE de `direccion` a proposito: el equipo pidio
        poder agrupar la carga por distrito, y para eso el campo tiene que
        existir por si mismo. Si el distrito viajara embebido dentro de la
        direccion, cada agrupacion dependeria de parsear texto libre.
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
        """Corrige un pedido ya registrado.

        Solo se modifican los campos que llegan informedos: `None` significa
        "no tocar". Esa distincion importa porque el formulario de edicion
        se rellena con los valores actuales del pedido, y un campo vacio
        tiene que poder guardarse como vacio y no interpretarse como
        "dejarlo como estaba".
        """
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
        """Aplica la misma correccion a varios pedidos de una vez.

        Es el caso de uso real en una tienda: "estos 40 pedidos son del mismo
        cliente" o "este lote va a La Castilla". Editarlos uno por uno seria
        lento y propenso a errores, y ademas escribiria el archivo 40 veces.

        Se valida el peso UNA vez antes de tocar nada. Si fuera invalido, el
        cambio se rechaza en bloque en lugar de aplicarse a los primeros y
        fallar en el ultimo: un estado a medio cambiar es peor que no
        cambiar nada.
        """
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
        """Analiza un archivo CSV, TXT o XLSX SIN registrar nada.

        Devuelve la lista de pedidos que se importarian junto con el detalle
        de las filas rechazadas, pero no toca el sistema. Quien llama decide
        si confirma con `confirmar_importacion`.

        La separacion en dos pasos responde a la observacion del equipo: si
        la subida confirmara automaticamente, un archivo equivocado cargaria
        pedidos que despues habria que borrar uno por uno. Con la vista
        previa se ve "van 48 pedidos y 2 filas con error" ANTES de decidir.
        """
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

        mensaje = resultado.resumen()

        if resultado.total_errores:
            mensaje += f" Primer error: fila {resultado.errores[0].linea}, {resultado.errores[0].mensaje}"

        mensaje += " Confirme la importacion para guardarlos."

        return ResultadoOperacion.exito(mensaje, resultado)

    def confirmar_importacion(self, resultado: ResultadoImportacion) -> ResultadoOperacion:
        """Registra de verdad los pedidos de una vista previa ya revisada.

        Acepta el resultado que devolvio `importar` tal cual. Es la segunda
        mitad del flujo en dos pasos y mantiene la responsabilidad en el
        nucleo: la interfaz solo decide si confirmar, nunca escribe en el
        almacen.
        """
        if resultado is None or not resultado.pedidos:
            return ResultadoOperacion.error("No hay pedidos para confirmar.")

        for pedido in resultado.pedidos:
            pedido.fecha_registro = ahora()
            self.repositorio.agregar(pedido)
            self.repositorio.contador += 1

        self.repositorio.guardar()

        mensaje = resultado.resumen()

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
        campo: CampoOrden = CampoOrden.PESO,
        distrito: Optional[str] = None,
    ) -> List[Pedido]:
        """Lista pedidos con filtros de peso y distrito, y orden opcional.

        El filtro se aplica ANTES de ordenar: filtrar despues obligaria a
        ordenar elementos que despues se descartan, que es trabajo perdido.

        `campo` decide POR QUE se ordena. Si es el peso, se aplica el
        algoritmo indicado en `orden`, que es lo que el curso evalua. Si es
        el codigo o el distrito se usa el comparador nativo, porque los
        algoritmos de conteo y cubetas necesitan enteros en un rango acotado
        y esos dos campos son texto.
        """
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
        """Devuelve la funcion `key` para ordenar por el campo pedido.

        El distrito se compara en minusculas y sin acentos para que "La
        Castilla" y "la castilla" caigan en el mismo grupo al ordenar. Sin
        esa normalizacion el ordenamiento alfabetico pondria cada variante
        en un lado distinto de la lista, que es justo lo contrario de agrupar.
        """
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
        """Simula la salida de UN viaje SIN modificar el sistema.

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
        """Simula el reparto completo en uno o varios viajes.

        `viajes = 0` significa "todos los que hagan falta": es el valor por
        defecto porque era justo lo que faltaba antes, un plan que solo
        resolvia una mochila y dejaba el resto de los pedidos sin destino
        visible. Con un numero mayor que cero se limita a esa cantidad.

        Devuelve un `PlanCarga`, que ademas de la lista de viajes incluye
        `no_asignados` con el motivo de cada pedido que no cupo.
        """
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
        """Despacha TODOS los viajes de un plan multi-viaje de una vez.

        Los pedidos de cada viaje quedan `DESPACHADO` con su fecha, y la
        salida se registra con el detalle de lo que llevo cada viaje. Es la
        operacion que corresponde a "hoy salen tres viajes".
        """
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
        detalle: List[Dict[str, Any]] = []

        for pedido in plan.seleccionados:
            pedido.estado = EstadoPedido.DESPACHADO
            pedido.fecha_despacho = momento
            codigos.append(pedido.codigo)
            detalle.append(
                {
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
        """Devuelve una salida concreta con el detalle de lo que llevo.

        Es el caso de uso que faltaba: tras confirmar, el historial solo
        mostraba un numero de pedidos y un peso. Con esto se puede abrir
        cada salida y ver pedido por pedido que salio, en que viaje y a que
        distrito.
        """
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
            # Suma kilos del tramo para enriquecer las graficas.
            pesos_tramo = [p for p in pedidos if p.peso >= inicio and p.peso < fin]
            if indice == intervalos - 1:
                pesos_tramo = [p for p in pedidos if p.peso >= inicio and p.peso <= mayor]
            grupo["peso"] = round(sum(p.peso for p in pesos_tramo), 2)

        return grupos

    def _distribucion_distritos(self, pedidos: Sequence[Pedido]) -> List[Dict[str, Any]]:
        """Cuenta pedidos y kilos por distrito.

        Usa el campo `distrito` ya separado de la direccion. Para los datos
        anteriores a ese campo, `distrito_efectivo` deduce el valor del
        texto tras la ultima coma, de modo que el agrupamiento tambien
        funciona sobre los pedidos que ya estaban guardados.

        Se agrupa por la version normalizada pero se MUESTRA la forma
        original: asi "La Castilla" y "la castilla" cuentan como un solo
        distrito sin que la pantalla muestre dos nombres distintos del mismo
        lugar.
        """
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
