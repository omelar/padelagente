import os
import yaml
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def cargar_config_prompts() -> dict:
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo en unos minutos.")


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpa, no entendí tu mensaje. ¿Puedes repetirlo de otra forma? 😊")


def construir_system_prompt(jugador: dict | None) -> str:
    """Construye el system prompt adaptado según si el jugador está registrado o no."""
    config = cargar_config_prompts()
    base = config.get("system_prompt", "Eres un asistente útil. Responde en español.")

    if jugador is None:
        # Jugador nuevo — modo registro
        extra = """

## ESTADO ACTUAL: JUGADOR NO REGISTRADO
Este jugador escribe por PRIMERA VEZ. Debes registrarlo antes de cualquier otra cosa.

Sigue este flujo exacto, UNA pregunta a la vez:
1. Dale la bienvenida al club
2. Pregunta su nombre completo
3. Pregunta su nivel de juego:
   - 1️⃣ Iniciación (empezando o menos de 1 año)
   - 2️⃣ Intermedio (1-3 años, juegas con regularidad)
   - 3️⃣ Avanzado (más de 3 años, compites o entrenas)
4. Cuando tengas nombre Y nivel, incluye AL FINAL de tu respuesta (en una línea separada):
   [REGISTRAR:nombre completo:nivel]
   Donde nivel es exactamente: iniciacion, intermedio o avanzado

Ejemplo de marcador: [REGISTRAR:Juan García:intermedio]

IMPORTANTE: No hagas nada más hasta completar el registro.
"""
    else:
        # Jugador registrado — modo normal con su contexto
        extra = f"""

## ESTADO ACTUAL: JUGADOR REGISTRADO
Nombre: {jugador['nombre']}
Nivel: {jugador['nivel']}

Salúdale por su nombre. Ya está registrado, puedes atenderle directamente.

## Función de emparejamiento
Si el jugador quiere reservar una pista pero dice que va solo o que no tiene compañeros,
ofrécele buscar otros jugadores de su mismo nivel ({jugador['nivel']}).

Si acepta, pregunta fecha y hora. Cuando tengas ambos datos, incluye AL FINAL de tu respuesta:
[BUSCAR_JUGADORES:{jugador['nivel']}:fecha:hora]

Ejemplo: [BUSCAR_JUGADORES:intermedio:23/04/2026:18:00]

El sistema enviará automáticamente mensajes a otros jugadores del mismo nivel.
"""

    return base + extra


async def generar_respuesta(mensaje: str, historial: list[dict], jugador: dict | None = None) -> str:
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = construir_system_prompt(jugador)

    mensajes = []
    for msg in historial:
        mensajes.append({"role": msg["role"], "content": msg["content"]})
    mensajes.append({"role": "user", "content": mensaje})

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes
        )

        respuesta = response.content[0].text
        logger.info(f"Respuesta generada ({response.usage.input_tokens} in / {response.usage.output_tokens} out)")
        return respuesta

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()
