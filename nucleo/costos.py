"""Tarifas comerciales referenciales desde Miraflores."""
from decimal import Decimal, ROUND_HALF_UP
import unicodedata

TARIFAS_INICIALES = {
    "Miraflores": 2.0, "San Isidro": 2.0, "Surco": 2.0,
    "Barranco": 2.0, "Surquillo": 2.0, "San Borja": 2.0,
    "Lince": 3.0, "Jesus Maria": 3.0,
    "Los Olivos": 4.0, "Independencia": 4.0,
}

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).lower().split())

def cotizar(peso, distrito, tarifas=None):
    tarifas = TARIFAS_INICIALES if tarifas is None else tarifas
    clave = normalizar(distrito)
    if clave == "santiago de surco":
        clave = "surco"
    for nombre, tarifa in tarifas.items():
        if clave == normalizar(nombre) and tarifa is not None:
            costo = (Decimal(str(peso)) * Decimal(str(tarifa))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return {"tarifa_kg": tarifa, "costo_envio": float(costo)}
    return {"tarifa_kg": None, "costo_envio": None}

def resumir_costos(detalle):
    pendientes = sum(p.get("costo_envio") is None for p in detalle)
    subtotal = sum((Decimal(str(p["costo_envio"])) for p in detalle if p.get("costo_envio") is not None), Decimal(0))
    return {"costo_total": None if pendientes else float(subtotal), "costo_cotizado": float(subtotal), "costos_pendientes": pendientes}
