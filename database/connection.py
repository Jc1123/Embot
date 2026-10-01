import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite


class Database:
    def __init__(self, path: str):
        self.path = path
        self._connection: aiosqlite.Connection | None = None
        self._transaction_lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._connection is not None:
            return

        self._connection = await aiosqlite.connect(
            self.path
        )

        self._connection.row_factory = aiosqlite.Row

        await self._connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        await self._connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        await self._connection.execute(
            "PRAGMA busy_timeout = 5000"
        )

        await self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    def _require_connection(
        self
    ) -> aiosqlite.Connection:

        if self._connection is None:
            raise RuntimeError(
                "Banco de dados não conectado."
            )

        return self._connection

    @asynccontextmanager
    async def transaction(
        self
    ) -> AsyncIterator[aiosqlite.Connection]:

        db = self._require_connection()

        async with self._transaction_lock:

            await db.execute(
                "BEGIN IMMEDIATE"
            )

            try:
                yield db

            except Exception:
                await db.rollback()
                raise

            else:
                await db.commit()

    async def initialize(self) -> None:
        db = self._require_connection()

        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sorteios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                id_cripto TEXT NOT NULL UNIQUE,

                titulo TEXT NOT NULL,

                descricao TEXT NOT NULL,

                timestamp_termino INTEGER NOT NULL,

                organizador_id INTEGER NOT NULL,

                ganhadores INTEGER NOT NULL
                    CHECK (ganhadores > 0),

                canal_id INTEGER NOT NULL,

                mensagem_id INTEGER NOT NULL DEFAULT 0,

                ativo INTEGER NOT NULL DEFAULT 1
                    CHECK (ativo IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS participantes (
                id_cripto TEXT NOT NULL,

                user_id INTEGER NOT NULL,

                PRIMARY KEY (
                    id_cripto,
                    user_id
                ),

                FOREIGN KEY (
                    id_cripto
                )
                REFERENCES sorteios(id_cripto)
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_sorteios_ativos_termino
            ON sorteios (
                ativo,
                timestamp_termino
            );

            CREATE INDEX IF NOT EXISTS
                idx_sorteios_mensagem_ativa
            ON sorteios (
                mensagem_id,
                ativo
            );

            CREATE TABLE IF NOT EXISTS farm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                farm_key TEXT NOT NULL,

                user_id INTEGER NOT NULL,

                user_name TEXT NOT NULL,

                started_at INTEGER NOT NULL,

                ends_at INTEGER NOT NULL,

                CHECK (ends_at > started_at)
            );

            CREATE INDEX IF NOT EXISTS
                idx_farm_usage_farm_termino
            ON farm_usage (
                farm_key,
                ends_at
            );

            CREATE INDEX IF NOT EXISTS
                idx_farm_usage_termino
            ON farm_usage (
                ends_at
            );
            """
        )

        await db.commit()