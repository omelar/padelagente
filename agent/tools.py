import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")

# Contador simple de reservas en memoria (en producción usar base de datos)
_reservas = {}
_contador_reservas = 0


def cargar_info_negocio() -> dict:
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    info = cargar_info_negocio()
    ahora = datetime.now()
    hora_actual = ahora.hour + ahora.minute / 60
    esta_abierto = 8.0 <= hora_actual < 23.0
    return {
        "horario": info.get("negocio", {}).get("horario", "Todos los días de 8:00 a 23:00"),
        "esta_abierto": esta_abierto,
    }


def crear_reserva(telefono: str, nombre: str, fecha: str, hora: str, num_jugadores: int) -> dict:
    """Registra una reserva de pista de pádel."""
    global _contador_reservas
    _contador_reservas += 1
    codigo = f"PAD-{_contador_reservas:03d}"

    reserva = {
        "codigo": codigo,
        "telefono": telefono,
        "nombre": nombre,
        "fecha": fecha,
        "hora": hora,
        "num_jugadores": num_jugadores,
        "estado": "confirmada",
        "creada_en": datetime.now().isoformat(),
    }

    _reservas[codigo] = reserva
    logger.info(f"Reserva creada: {codigo} — {nombre} para {fecha} a las {hora}")
    return reserva


def consultar_reserva(codigo: str) -> dict | None:
    """Busca una reserva por su código."""
    return _reservas.get(codigo.upper())


def cancelar_reserva(codigo: str) -> bool:
    """Cancela una reserva existente."""
    if codigo.upper() in _reservas:
        _reservas[codigo.upper()]["estado"] = "cancelada"
        logger.info(f"Reserva cancelada: {codigo}")
        return True
    return False


def listar_reservas_telefono(telefono: str) -> list[dict]:
    """Retorna todas las reservas activas de un número de teléfono."""
    return [
        r for r in _reservas.values()
        if r["telefono"] == telefono and r["estado"] == "confirmada"
    ]
