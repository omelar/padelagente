import os
import re
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import (
    inicializar_db, guardar_mensaje, obtener_historial,
    obtener_jugador, registrar_jugador, buscar_jugadores_nivel
)
from agent.providers import obtener_proveedor

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="Asistente del Club — Omelar Pádel",
    version="1.0.0",
    lifespan=lifespan
)


def extraer_marcador(respuesta: str, patron: str) -> tuple[str, str | None]:
    """Extrae un marcador de la respuesta y retorna (respuesta_limpia, valor_marcador)."""
    match = re.search(patron, respuesta)
    if match:
        respuesta_limpia = respuesta[:match.start()].strip()
        return respuesta_limpia, match.group(0)
    return respuesta, None


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "agentkit", "agente": "Asistente del Club"}


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            jugador = await obtener_jugador(msg.telefono)
            historial = await obtener_historial(msg.telefono)
            respuesta = await generar_respuesta(msg.texto, historial, jugador)

            # Procesar marcador de registro
            respuesta, marcador_registro = extraer_marcador(
                respuesta, r'\[REGISTRAR:([^:]+):([^\]]+)\]'
            )
            if marcador_registro:
                match = re.search(r'\[REGISTRAR:([^:]+):([^\]]+)\]', marcador_registro)
                if match:
                    nombre, nivel = match.group(1).strip(), match.group(2).strip()
                    jugador = await registrar_jugador(msg.telefono, nombre, nivel)
                    logger.info(f"Jugador registrado: {nombre} — nivel {nivel}")

            # Procesar marcador de búsqueda de jugadores
            respuesta, marcador_busqueda = extraer_marcador(
                respuesta, r'\[BUSCAR_JUGADORES:([^:]+):([^:]+):([^\]]+)\]'
            )
            if marcador_busqueda:
                match = re.search(r'\[BUSCAR_JUGADORES:([^:]+):([^:]+):([^\]]+)\]', marcador_busqueda)
                if match:
                    nivel_busqueda = match.group(1).strip()
                    fecha = match.group(2).strip()
                    hora = match.group(3).strip()
                    candidatos = await buscar_jugadores_nivel(nivel_busqueda, msg.telefono)

                    if candidatos:
                        solicitante = jugador["nombre"] if jugador else "Un jugador"
                        for candidato in candidatos[:3]:
                            aviso = (
                                f"Hola {candidato['nombre']} 🎾 {solicitante} busca compañeros "
                                f"de nivel {nivel_busqueda} para jugar el {fecha} a las {hora}. "
                                f"¿Te apuntas? Responde SÍ o NO."
                            )
                            await proveedor.enviar_mensaje(candidato["telefono"], aviso)
                            logger.info(f"Aviso enviado a {candidato['nombre']} ({candidato['telefono']})")
                    else:
                        respuesta += "\n\nAún no hay otros jugadores de tu nivel registrados en el sistema. En cuanto se registren más, podrás encontrar compañeros fácilmente 😊"

            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)
            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"Respuesta a {msg.telefono}: {respuesta}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
