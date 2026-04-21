import asyncio
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.brain import generar_respuesta
from agent.memory import (
    inicializar_db, guardar_mensaje, obtener_historial, limpiar_historial,
    obtener_jugador, registrar_jugador, buscar_jugadores_nivel
)

TELEFONO_TEST = "test-local-001"


def extraer_marcador(respuesta: str, patron: str):
    match = re.search(patron, respuesta)
    if match:
        return respuesta[:match.start()].strip(), match.group(0)
    return respuesta, None


async def main():
    await inicializar_db()

    print()
    print("=" * 55)
    print("   Asistente del Club — Omelar Pádel (Test Local)")
    print("=" * 55)
    print()
    print("  Escribe mensajes como si fueras un jugador.")
    print("  Comandos especiales:")
    print("    'limpiar'  — borra el historial y registro")
    print("    'salir'    — termina el test")
    print()
    print("-" * 55)
    print()

    while True:
        try:
            mensaje = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nTest finalizado.")
            break

        if not mensaje:
            continue

        if mensaje.lower() == "salir":
            print("\nTest finalizado.")
            break

        if mensaje.lower() == "limpiar":
            await limpiar_historial(TELEFONO_TEST)
            print("[Historial y registro borrados]\n")
            continue

        jugador = await obtener_jugador(TELEFONO_TEST)
        historial = await obtener_historial(TELEFONO_TEST)

        print("\nAsistente del Club: ", end="", flush=True)
        respuesta = await generar_respuesta(mensaje, historial, jugador)

        # Procesar marcador de registro
        respuesta, marcador_registro = extraer_marcador(
            respuesta, r'\[REGISTRAR:([^:]+):([^\]]+)\]'
        )
        if marcador_registro:
            match = re.search(r'\[REGISTRAR:([^:]+):([^\]]+)\]', marcador_registro)
            if match:
                nombre, nivel = match.group(1).strip(), match.group(2).strip()
                await registrar_jugador(TELEFONO_TEST, nombre, nivel)
                print(f"[Sistema: jugador registrado — {nombre}, nivel {nivel}]")

        # Procesar marcador de búsqueda
        respuesta, marcador_busqueda = extraer_marcador(
            respuesta, r'\[BUSCAR_JUGADORES:([^:]+):([^:]+):([^\]]+)\]'
        )
        if marcador_busqueda:
            match = re.search(r'\[BUSCAR_JUGADORES:([^:]+):([^:]+):([^\]]+)\]', marcador_busqueda)
            if match:
                nivel_busqueda, fecha, hora = match.group(1), match.group(2), match.group(3)
                candidatos = await buscar_jugadores_nivel(nivel_busqueda, TELEFONO_TEST)
                if candidatos:
                    print(f"\n[Sistema: enviando aviso a {len(candidatos)} jugador(es) de nivel {nivel_busqueda}]")
                    for c in candidatos:
                        print(f"  → WhatsApp a {c['nombre']} ({c['telefono']}): buscando compañeros para {fecha} a las {hora}")
                else:
                    respuesta += "\n\nAún no hay otros jugadores de tu nivel registrados. En cuanto se registren más, podrás encontrar compañeros 😊"

        print(respuesta)
        print()

        await guardar_mensaje(TELEFONO_TEST, "user", mensaje)
        await guardar_mensaje(TELEFONO_TEST, "assistant", respuesta)


if __name__ == "__main__":
    asyncio.run(main())
