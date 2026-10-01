import hashlib
from dataclasses import dataclass
from uuid import uuid4

from .connection import Database


@dataclass(frozen=True, slots=True)
class Giveaway:
    id_cripto: str
    titulo: str
    descricao: str
    timestamp_termino: int
    organizador_id: int
    ganhadores: int
    canal_id: int
    mensagem_id: int


def generate_id_hash(
    numero_sorteio: int
) -> str:

    base = f"{numero_sorteio}-Embrapa"

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()[:10]


class GiveawayRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        titulo: str,
        descricao: str,
        timestamp_termino: int,
        organizador_id: int,
        ganhadores: int,
        canal_id: int,
    ) -> str:

        async with self.db.transaction() as conn:

            cursor = await conn.execute(
                """
                INSERT INTO sorteios
                    (
                        id_cripto,
                        titulo,
                        descricao,
                        timestamp_termino,
                        organizador_id,
                        ganhadores,
                        canal_id
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"pending-{uuid4().hex}",
                    titulo,
                    descricao,
                    timestamp_termino,
                    organizador_id,
                    ganhadores,
                    canal_id,
                ),
            )

            internal_id = cursor.lastrowid

            id_cripto = generate_id_hash(
                internal_id
            )

            await conn.execute(
                """
                UPDATE sorteios
                SET id_cripto = ?
                WHERE id = ?
                """,
                (
                    id_cripto,
                    internal_id
                ),
            )

        return id_cripto

    async def set_message_id(
        self,
        id_cripto: str,
        mensagem_id: int
    ) -> bool:

        async with self.db.transaction() as conn:

            cursor = await conn.execute(
                """
                UPDATE sorteios

                SET mensagem_id = ?

                WHERE id_cripto = ?
                AND ativo = 1
                """,
                (
                    mensagem_id,
                    id_cripto
                ),
            )

            return cursor.rowcount > 0

    async def deactivate(
        self,
        id_cripto: str
    ) -> None:

        async with self.db.transaction() as conn:

            await conn.execute(
                """
                UPDATE sorteios
                SET ativo = 0
                WHERE id_cripto = ?
                """,
                (id_cripto,),
            )

    async def get_active_by_message(
        self,
        mensagem_id: int
    ) -> tuple[str, int] | None:

        db = self.db._require_connection()

        cursor = await db.execute(
            """
            SELECT
                id_cripto,
                organizador_id

            FROM sorteios

            WHERE mensagem_id = ?
            AND ativo = 1
            """,
            (mensagem_id,),
        )

        row = await cursor.fetchone()

        await cursor.close()

        if row is None:
            return None

        return (
            row["id_cripto"],
            row["organizador_id"]
        )

    async def add_participant(
        self,
        id_cripto: str,
        user_id: int
    ) -> tuple[bool, int]:

        async with self.db.transaction() as conn:

            cursor = await conn.execute(
                """
                INSERT OR IGNORE INTO participantes
                    (
                        id_cripto,
                        user_id
                    )

                SELECT ?, ?

                WHERE EXISTS (
                    SELECT 1
                    FROM sorteios

                    WHERE id_cripto = ?
                    AND ativo = 1
                )
                """,
                (
                    id_cripto,
                    user_id,
                    id_cripto
                ),
            )

            inserted = cursor.rowcount > 0

            cursor = await conn.execute(
                """
                SELECT COUNT(*)

                FROM participantes

                WHERE id_cripto = ?
                """,
                (id_cripto,),
            )

            row = await cursor.fetchone()

            total = int(row[0])

            return inserted, total

    async def get_expired_ids(
        self,
        timestamp_atual: int
    ) -> list[str]:

        db = self.db._require_connection()

        cursor = await db.execute(
            """
            SELECT id_cripto

            FROM sorteios

            WHERE ativo = 1
            AND timestamp_termino <= ?

            ORDER BY timestamp_termino ASC
            """,
            (timestamp_atual,),
        )

        rows = await cursor.fetchall()

        await cursor.close()

        return [
            row[0]
            for row in rows
        ]

    async def finalize_and_get_data(
        self,
        id_cripto: str
    ) -> tuple[Giveaway, list[int]] | None:

        async with self.db.transaction() as conn:

            cursor = await conn.execute(
                """
                SELECT
                    id_cripto,
                    titulo,
                    descricao,
                    timestamp_termino,
                    organizador_id,
                    ganhadores,
                    canal_id,
                    mensagem_id

                FROM sorteios

                WHERE id_cripto = ?
                AND ativo = 1
                """,
                (id_cripto,),
            )

            row = await cursor.fetchone()

            if row is None:
                return None

            cursor = await conn.execute(
                """
                SELECT user_id

                FROM participantes

                WHERE id_cripto = ?
                """,
                (id_cripto,),
            )

            participants = [
                int(r[0])
                for r in await cursor.fetchall()
            ]

            await conn.execute(
                """
                UPDATE sorteios

                SET ativo = 0

                WHERE id_cripto = ?
                AND ativo = 1
                """,
                (id_cripto,),
            )

            giveaway = Giveaway(
                id_cripto=row["id_cripto"],
                titulo=row["titulo"],
                descricao=row["descricao"],
                timestamp_termino=row[
                    "timestamp_termino"
                ],
                organizador_id=row[
                    "organizador_id"
                ],
                ganhadores=row["ganhadores"],
                canal_id=row["canal_id"],
                mensagem_id=row["mensagem_id"],
            )

            return giveaway, participants

    async def get_active(
        self,
        id_cripto: str
    ) -> Giveaway | None:

        db = self.db._require_connection()

        cursor = await db.execute(
            """
            SELECT
                id_cripto,
                titulo,
                descricao,
                timestamp_termino,
                organizador_id,
                ganhadores,
                canal_id,
                mensagem_id

            FROM sorteios

            WHERE id_cripto = ?
            AND ativo = 1
            """,
            (id_cripto,),
        )

        row = await cursor.fetchone()

        await cursor.close()

        if row is None:
            return None

        return Giveaway(
            id_cripto=row["id_cripto"],
            titulo=row["titulo"],
            descricao=row["descricao"],
            timestamp_termino=row[
                "timestamp_termino"
            ],
            organizador_id=row[
                "organizador_id"
            ],
            ganhadores=row["ganhadores"],
            canal_id=row["canal_id"],
            mensagem_id=row["mensagem_id"],
        )