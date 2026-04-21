import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, select, Integer, Boolean
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Mensaje(Base):
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Jugador(Base):
    __tablename__ = "jugadores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    nivel: Mapped[str] = mapped_column(String(20))  # iniciacion, intermedio, avanzado
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def inicializar_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def guardar_mensaje(telefono: str, role: str, content: str):
    async with async_session() as session:
        mensaje = Mensaje(
            telefono=telefono,
            role=role,
            content=content,
            timestamp=datetime.utcnow()
        )
        session.add(mensaje)
        await session.commit()


async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:
    async with async_session() as session:
        query = (
            select(Mensaje)
            .where(Mensaje.telefono == telefono)
            .order_by(Mensaje.timestamp.desc())
            .limit(limite)
        )
        result = await session.execute(query)
        mensajes = result.scalars().all()
        mensajes.reverse()
        return [{"role": msg.role, "content": msg.content} for msg in mensajes]


async def limpiar_historial(telefono: str):
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono)
        result = await session.execute(query)
        mensajes = result.scalars().all()
        for msg in mensajes:
            await session.delete(msg)
        await session.commit()


async def registrar_jugador(telefono: str, nombre: str, nivel: str) -> dict:
    """Registra un jugador nuevo o actualiza sus datos si ya existe."""
    async with async_session() as session:
        query = select(Jugador).where(Jugador.telefono == telefono)
        result = await session.execute(query)
        jugador = result.scalar_one_or_none()

        if jugador:
            jugador.nombre = nombre
            jugador.nivel = nivel.lower()
        else:
            jugador = Jugador(
                telefono=telefono,
                nombre=nombre,
                nivel=nivel.lower(),
                fecha_registro=datetime.utcnow()
            )
            session.add(jugador)

        await session.commit()
        return {"telefono": jugador.telefono, "nombre": jugador.nombre, "nivel": jugador.nivel}


async def obtener_jugador(telefono: str) -> dict | None:
    """Retorna los datos de un jugador o None si no está registrado."""
    async with async_session() as session:
        query = select(Jugador).where(Jugador.telefono == telefono, Jugador.activo == True)
        result = await session.execute(query)
        jugador = result.scalar_one_or_none()
        if not jugador:
            return None
        return {"telefono": jugador.telefono, "nombre": jugador.nombre, "nivel": jugador.nivel}


async def buscar_jugadores_nivel(nivel: str, excluir_telefono: str, limite: int = 10) -> list[dict]:
    """Busca jugadores activos del mismo nivel, excluyendo al solicitante."""
    async with async_session() as session:
        query = (
            select(Jugador)
            .where(
                Jugador.nivel == nivel.lower(),
                Jugador.activo == True,
                Jugador.telefono != excluir_telefono
            )
            .limit(limite)
        )
        result = await session.execute(query)
        jugadores = result.scalars().all()
        return [{"telefono": j.telefono, "nombre": j.nombre, "nivel": j.nivel} for j in jugadores]
