"""
 nucleo.importador
 =================

 Carga masiva de pedidos desde archivos CSV, TXT o XLSX (Excel).

 En vez de exigir un formato unico y rigido, el importador DETECTA las
 columnas por nombre de encabezado. Asi un archivo con las columnas
 `Peso`, `Direccion`, `Cliente` o `weight,address` se carga igual, y el
 usuario no tiene que renombrar nada.

 Cada fila se valida de forma independiente: si la fila 3 tiene un peso de
 "abc", se registra el error con su numero de fila y las demas filas se
 importan igual. Un archivo con 500 pedidos donde uno esta malo importa 499
 en vez de nada, que es el comportamiento que espera cualquier usuario.

 Para Excel se usa `openpyxl`, que es una dependencia OPCIONAL: si no esta
 instalada, el importador de .xlsx avisa con un mensaje claro y el resto de
 formatos siguen funcionando.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .modelos import PESO_MAXIMO_KG, PESO_MINIMO_KG, Pedido

#: Palabras clave para reconocer cada columna, en español y en inglés.
#: La lista de un campo se prueba con `in`, no con igualdad, para que
#: "Distrito de entrega" se reconozca igual que "distrito".
CLAVES_PESO = ("peso", "peso_kg", "kg", "kilo", "weight", "peso_envio")
CLAVES_DISTRITO = ("distrito", "barrio", "localidad", "zona", "sector", "district")
CLAVES_DIRECCION = ("direccion", "address", "destino", "domicilio", "dir")
CLAVES_CLIENTE = ("cliente", "nombre", "customer", "name", "destinatario")
CLAVES_TELEFONO = ("telefono", "phone", "celular", "movil", "contacto", "numero")

#: Separadores aceptados en archivos CSV.
DELIMITADORES = (";", ",", "\t", "|")


@dataclass
class ErrorImportacion:
    """Fila rechazada, con su numero de linea y el motivo."""

    linea: int
    mensaje: str
    contenido: str = ""

    def a_dict(self) -> Dict[str, Any]:
        return {"linea": self.linea, "mensaje": self.mensaje, "contenido": self.contenido}


@dataclass
class ResultadoImportacion:
    """Resultado de procesar un archivo completo."""

    pedidos: List[Pedido] = field(default_factory=list)
    errores: List[ErrorImportacion] = field(default_factory=list)
    filas_leidas: int = 0
    formato: str = ""

    @property
    def total_importados(self) -> int:
        return len(self.pedidos)

    @property
    def total_errores(self) -> int:
        return len(self.errores)

    @property
    def peso_total(self) -> float:
        return round(sum(pedido.peso for pedido in self.pedidos), 2)

    def resumen(self) -> str:
        if self.filas_leidas == 0:
            return "El archivo no contenia filas de datos."

        partes = [
            f"{self.total_importados} pedido(s) importado(s)",
            f"{round(self.peso_total, 2)} kg en total",
        ]

        if self.total_errores:
            partes.append(f"{self.total_errores} fila(s) con error")

        return ", ".join(partes) + "."

    def a_dict(self) -> Dict[str, Any]:
        return {
            "pedidos": [pedido.a_dict() for pedido in self.pedidos],
            "errores": [error.a_dict() for error in self.errores],
            "filas_leidas": self.filas_leidas,
            "total_importados": self.total_importados,
            "total_errores": self.total_errores,
            "peso_total": self.peso_total,
            "formato": self.formato,
            "resumen": self.resumen(),
        }


# --------------------------------------------------------------------------
# Entrada principal
# --------------------------------------------------------------------------


def importar_archivo(nombre_archivo: str, contenido: bytes, codigos: Sequence[str]) -> ResultadoImportacion:
    """Punto de entrada: decide el parser segun la extension del archivo.

    Se recibe BYTES y no texto porque un .xlsx es un archivo binario (un ZIP)
    y no puede decodificarse como texto. La decodificacion a texto se hace
    recien dentro de cada parser, donde se sabe que el formato lo permite.
    """
    extension = nombre_archivo.rsplit(".", 1)[-1].lower() if "." in nombre_archivo else ""

    if extension == "csv":
        return _importar_csv(contenido, codigos)

    if extension == "txt":
        return _importar_txt(contenido, codigos)

    if extension in ("xlsx", "xlsm"):
        return _importar_excel(contenido, codigos)

    return ResultadoImportacion(
        formato=extension or "desconocido",
        errores=[
            ErrorImportacion(
                0,
                f"Formato '{extension or 'sin extension'}' no soportado. Usa CSV, TXT o XLSX.",
            )
        ],
    )


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def _importar_csv(contenido: bytes, codigos: Sequence[str]) -> ResultadoImportacion:
    """Importa un CSV detectando el separador automaticamente.

    `csv.Sniffer` examina las primeras filas y propone el delimitador. Se
    prueba cada candidato y se acepta el que produce mas columnas, porque
    Sniffer puede fallar con archivos de una sola columna o con separadores
    mixtos.
    """
    texto = _decodificar(contenido)
    resultado = ResultadoImportacion(formato="CSV")

    if not texto.strip():
        resultado.errores.append(ErrorImportacion(0, "El archivo esta vacio."))
        return resultado

    muestra = texto[:4096]
    delimitador = ","

    try:
        sniff = csv.Sniffer()
        candidato = sniff.sniff(muestra, delimiters="".join(DELIMITADORES))
        delimitador = candidato.delimiter
    except csv.Error:
        delimitador = max(
            (texto.count(d) for d in DELIMITADORES),
            key=lambda d: texto.count(d),
        ) if any(d in texto for d in DELIMITADORES) else ","

    filas = list(csv.reader(io.StringIO(texto), delimiter=delimitador))

    if not filas:
        resultado.errores.append(ErrorImportacion(0, "No se pudo leer el archivo."))
        return resultado

    return _procesar_tabla(filas, codigos, "CSV", tiene_encabezado=_parece_encabezado(filas[0]))


# --------------------------------------------------------------------------
# TXT
# --------------------------------------------------------------------------


def _importar_txt(contenido: bytes, codigos: Sequence[str]) -> ResultadoImportacion:
    """Importa un TXT de texto plano.

    Acepta los dos formatos mas comunes:

        5.5                          -> solo el peso
        5.5; Calle 10 #3-22         -> peso y direccion separados por `;`

    Las lineas en blanco y las que empiezan con `#` se ignoran, lo que
    permite documentar el archivo con comentarios.
    """
    texto = _decodificar(contenido)
    resultado = ResultadoImportacion(formato="TXT")

    filas: List[List[str]] = []

    for numero, linea in enumerate(texto.splitlines(), start=1):
        limpia = linea.strip()

        if not limpia or limpia.startswith("#"):
            continue

        if ";" in limpia:
            campos = [campo.strip() for campo in limpia.split(";")]
        elif "," in limpia:
            campos = [campo.strip() for campo in limpia.split(",")]
        else:
            campos = [limpia]

        filas.append(campos)

    if not filas:
        resultado.errores.append(ErrorImportacion(0, "El archivo no tiene datos."))
        return resultado

    # En TXT la primera fila tambien puede ser un encabezado con las
    # palabras clave; si lo es, se descarta.
    encabezado = _parece_encabezado(filas[0]) and len(filas[0]) > 1

    return _procesar_tabla(filas, codigos, "TXT", tiene_encabezado=encabezado)


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------


def _importar_excel(contenido: bytes, codigos: Sequence[str]) -> ResultadoImportacion:
    """Importa un .xlsx usando openpyxl (dependencia opcional)."""
    resultado = ResultadoImportacion(formato="XLSX")

    try:
        from openpyxl import load_workbook
    except ImportError:
        resultado.errores.append(
            ErrorImportacion(
                0,
                "El soporte de Excel requiere la libreria openpyxl. "
                "Instala con: pip install openpyxl  (CSV y TXT funcionan sin ella)",
            )
        )
        return resultado

    try:
        libro = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception as error:  # noqa: BLE001 - el parser debe degradar, no romper
        resultado.errores.append(
            ErrorImportacion(0, f"No se pudo leer el archivo Excel: {error}")
        )
        return resultado

    hoja = libro[libro.sheetnames[0]]

    filas: List[List[str]] = []
    for fila in hoja.iter_rows(values_only=True):
        if fila is None:
            continue

        if all(celda is None or str(celda).strip() == "" for celda in fila):
            continue

        filas.append(["" if celda is None else str(celda).strip() for celda in fila])

    libro.close()

    if not filas:
        resultado.errores.append(ErrorImportacion(0, "La hoja de Excel esta vacia."))
        return resultado

    return _procesar_tabla(filas, codigos, "XLSX", tiene_encabezado=_parece_encabezado(filas[0]))


# --------------------------------------------------------------------------
# Procesamiento comun a los tres formatos
# --------------------------------------------------------------------------


def _procesar_tabla(
    filas: List[List[str]],
    codigos: Sequence[str],
    formato: str,
    tiene_encabezado: bool = False,
) -> ResultadoImportacion:
    """Convierte una tabla de texto en pedidos, valido fila por fila.

    Este es el punto donde los tres formatos se unifican: CSV, TXT y XLSX
    producen una lista de listas, y a partir de aqui el proceso es el
    mismo. Esa separacion evita duplicar la logica de validacion tres veces.
    """
    resultado = ResultadoImportacion(formato=formato)

    if tiene_encabezado:
        mapa_columnas = _mapear_columnas(filas[0])
        cuerpo = filas[1:]
        numero_inicial = 2
    else:
        mapa_columnas = None
        cuerpo = filas
        numero_inicial = 1

    # Si hay encabezado pero ninguna columna reconocible, se informa: casi
    # siempre significa que el archivo tiene otro formato.
    if tiene_encabezado and (not mapa_columnas or "peso" not in mapa_columnas):
        resultado.errores.append(
            ErrorImportacion(
                1,
                "No se encontro ninguna columna de peso. Revisa que el "
                "encabezado incluya una columna 'Peso'.",
            )
        )
        return resultado

    resultado.filas_leidas = len(cuerpo)
    indice_codigo = 0

    for desplazamiento, fila in enumerate(cuerpo):
        numero_linea = numero_inicial + desplazamiento
        contenido = "; ".join(str(celda) for celda in fila if str(celda).strip())

        if not contenido:
            continue

        if mapa_columnas is not None and mapa_columnas:
            peso_texto, distrito, direccion, cliente, telefono = _extraer_con_encabezado(
                fila, mapa_columnas
            )
        else:
            peso_texto, distrito, direccion, cliente, telefono = _extraer_posicional(fila)

        error = _validar_peso(peso_texto)

        if error:
            resultado.errores.append(ErrorImportacion(numero_linea, error, contenido))
            continue

        if indice_codigo < len(codigos):
            codigo = codigos[indice_codigo]
        else:
            codigo = f"P{resultado.total_importados + 1:03d}"

        indice_codigo += 1

        resultado.pedidos.append(
            Pedido(
                codigo=codigo,
                peso=round(_a_float(peso_texto), 2),
                direccion=direccion,
                cliente=cliente,
                telefono=telefono,
                distrito=distrito,
            )
        )

    return resultado


def _mapear_columnas(encabezado: Sequence[str]) -> Optional[Dict[str, int]]:
    """Detecta en que indice esta cada columna relevante.

    Devuelve None si ninguna columna coincide con las palabras clave, lo
    que indica que el archivo no tiene el formato esperado. Devuelve un
    diccionario vacio si solo encontro columnas no utilizables.
    """
    mapa: Dict[str, int] = {}

    for indice, titulo in enumerate(encabezado):
        normalizado = _normalizar(titulo)

        if not normalizado:
            continue

        # El orden importa: "distrito" se prueba ANTES que "direccion" porque
        # ambos son claves posibles y un archivo con las dos columnas debe
        # mapear cada una a su campo. "barrio" y "zona" viven en el mismo
        # grupo porque significan lo mismo para agrupar la carga.
        if "peso" not in mapa and any(clave in normalizado for clave in CLAVES_PESO):
            mapa["peso"] = indice
        elif "distrito" not in mapa and any(clave in normalizado for clave in CLAVES_DISTRITO):
            mapa["distrito"] = indice
        elif "direccion" not in mapa and any(clave in normalizado for clave in CLAVES_DIRECCION):
            mapa["direccion"] = indice
        elif "cliente" not in mapa and any(clave in normalizado for clave in CLAVES_CLIENTE):
            mapa["cliente"] = indice
        elif "telefono" not in mapa and any(clave in normalizado for clave in CLAVES_TELEFONO):
            mapa["telefono"] = indice

    return mapa or None


def _extraer_con_encabezado(
    fila: Sequence[str], mapa: Dict[str, int]
) -> Tuple[str, str, str, str, str]:
    """Lee los valores usando el mapa de columnas detectado."""

    def valor(clave: str) -> str:
        indice = mapa.get(clave)
        if indice is None or indice >= len(fila):
            return ""
        return str(fila[indice]).strip()

    return (
        valor("peso"),
        valor("distrito"),
        valor("direccion"),
        valor("cliente"),
        valor("telefono"),
    )


def _extraer_posicional(fila: Sequence[str]) -> Tuple[str, str, str, str, str]:
    """Lee los valores por posicion, para archivos sin encabezado.

    El peso siempre va primero. Los campos siguientes se asignan por
    orden: distrito, direccion, cliente y telefono. Se reconoce el telefono
    porque es el unico que empieza por digito y mide 10 caracteres, lo que
    evita confundirlo con un nombre propio.

    Si NO hay distrito, se deduce de lo que sigue a la ultima coma de la
    direccion, que es donde venia escrito antes de separarlo. Asi un
    archivo antiguo sin columna de distrito sigue agrupando bien.
    """
    peso = str(fila[0]).strip() if len(fila) > 0 else ""
    distrito = ""
    direccion = ""
    cliente = ""
    telefono = ""

    for valor in [str(celda).strip() for celda in fila[1:]]:
        if not valor:
            continue

        digitos = "".join(caracter for caracter in valor if caracter.isdigit())

        if not telefono and len(digitos) == 10 and valor[0].isdigit():
            telefono = valor
        elif not direccion:
            direccion = valor
        elif not cliente:
            cliente = valor
        else:
            telefono = telefono or valor

    if direccion and "," in direccion:
        distrito = direccion.rsplit(",", 1)[-1].strip()

    return peso, distrito, direccion, cliente, telefono


def _validar_peso(texto: str) -> str:
    """Devuelve el mensaje de error, o cadena vacia si el peso es valido.

    La conversion se hace con `replace` para tolerar el formato con coma
    decimal que usa Excel en configuraciones regionales hispanicas: "2,5"
    son 2.5 kg, no dos mil quinientos.
    """
    if not texto:
        return "Falta el peso."

    try:
        peso = _a_float(texto)
    except ValueError:
        return f"Peso no numerico: '{texto}'"

    if peso < PESO_MINIMO_KG:
        return f"El peso debe ser mayor a 0 kg (recibido: {peso})"

    if peso > PESO_MAXIMO_KG:
        return f"El peso supera el maximo de {PESO_MAXIMO_KG:g} kg (recibido: {peso})"

    return ""


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def _a_float(texto: str) -> float:
    """Convierte texto a float admitiendo coma o punto decimal.

    El problema real es que "8,25" en la mayoria de los locales significa
    8.25, no 825. Un `float()` directo lanzaria ValueError y la fila se
    perderia, cuando el usuario si estaba escribiendo un peso correcto.

    Se desambigua por posicion: si hay punto Y coma, el ultimo de los dos
    separadores es el decimal (pista: "1.234,56" es formato europeo y
    "1,234.56" es formato anglosajon). Si hay un solo separador y esta
    seguido de exactamente 3 digitos, se interpreta como separador de miles
    ("1,500" son mil quinientos), porque un peso de 1.5 kg con tres
    decimales no tiene sentido en este dominio.
    """
    limpio = str(texto).strip().replace(" ", "").replace("\u00a0", "")

    if not limpio:
        raise ValueError("texto vacio")

    if "," in limpio and "." in limpio:
        if limpio.rfind(",") > limpio.rfind("."):
            limpio = limpio.replace(".", "").replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
    elif "," in limpio:
        entero, _, decimal = limpio.partition(",")
        if len(decimal) == 3 and len(entero) > 0:
            limpio = entero + decimal
        else:
            limpio = entero + "." + decimal

    return float(limpio)


def _decodificar(contenido: bytes) -> str:
    """Decodifica bytes a texto probando las codificaciones habituales.

    Los archivos exportados desde Excel en espanol suelen venir en latin-1
    o cp1252, no en utf-8. Intentar utf-8 primero y recurrir a latin-1
    evita el error `UnicodeDecodeError` que abortaria la importacion.
    """
    for codificacion in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue

    return contenido.decode("utf-8", errors="replace")


def _normalizar(texto: Any) -> str:
    """Pasa un encabezado a minusculas sin espacios ni acentos.

    Asi "Peso (kg)", "PESO", " peso" y "Peso:" se reconocen como la misma
    columna, sin obligar al usuario a acertar el formato exacto.
    """
    limpio = str(texto or "").strip().lower()

    for acento, base in (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("ñ", "n"), ("ü", "u"),
    ):
        limpio = limpio.replace(acento, base)

    return limpio.replace(" ", "").replace("_", "").replace("(", "").replace(")", "")


def _parece_encabezado(fila: Sequence[str]) -> bool:
    """Deduce si la primera fila es un encabezado y no un dato.

    La heuristica es que un encabezado tiene texto no numerico Y alguna
    palabra clave conocida. Un dato, en cambio, empieza por un numero.
    """
    if not fila:
        return False

    primera = str(fila[0]).strip()

    if not primera:
        return False

    try:
        _a_float(primera)
        return False
    except ValueError:
        pass

    normalizado = _normalizar(primera)

    return any(
        clave.replace("_", "") in normalizado
        for clave in CLAVES_PESO + CLAVES_DIRECCION
    )


def plantilla_csv() -> str:
    """Contenido de ejemplo para que el usuario vea el formato."""
    return (
        "Peso,Distrito,Direccion,Cliente,Telefono\n"
        "2.50,La Castilla,Calle 10 #3-22,Ana García,3001234567\n"
        "18.00,El Cedro,Carrera 45 #12-08,Juan Rodríguez,3109876543\n"
        "7.25,La Flora,Avenida 80 #45-30,María López,3215554433\n"
        "12.00,La Castilla,Transversal 22 #5-14,Pedro Gómez,3009988776\n"
    )
