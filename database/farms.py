from dataclasses import dataclass

from .connection import Database


@dataclass(frozen=True, slots=True)
class FarmUsage:
    id: int
    farm_key: str
    user_id: int
    user_name: str
    started_at: int
    ends_at: int


class FarmRepository:
    def __init__(self, db: Database):
        self.db = db

    async def get_active(
        self,
        farm_key: str,
        timestamp_atual: int
    ) -> FarmUsage | None:
        db = self.db._require_connection()

        cursor = await db.execute(
            """
            SELECT
                id,
                farm_key,
                user_id,
                user_name,
                started_at,
                ends_at
            FROM farm_usage
            WHERE farm_key = ?
            AND ends_at > ?
            ORDER BY ends_at ASC
            LIMIT 1
            """,
            (farm_key, timestamp_atual),
        )

        row = await cursor.fetchone()
        await cursor.close()

        if row is None:
            return None

        return FarmUsage(
            id=row["id"],
            farm_key=row["farm_key"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            started_at=row["started_at"],
            ends_at=row["ends_at"],
        )

    async def get_active_by_user(
        self,
        user_id: int,
        timestamp_atual: int
    ) -> list[FarmUsage]:
        db = self.db._require_connection()

        cursor = await db.execute(
            """
            SELECT
                id,
                farm_key,
                user_id,
                user_name,
                started_at,
                ends_at
            FROM farm_usage
            WHERE user_id = ?
            AND ends_at > ?
            ORDER BY ends_at ASC
            """,
            (user_id, timestamp_atual),
        )

        rows = await cursor.fetchall()
        await cursor.close()

        return [
            FarmUsage(
                id=row["id"],
                farm_key=row["farm_key"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                started_at=row["started_at"],
                ends_at=row["ends_at"],
            )
            for row in rows
        ]

    async def get_active_by_user_and_farm(
        self,
        user_id: int,
        farm_key: str,
        timestamp_atual: int
    ) -> FarmUsage | None:
        db = self.db._require_connection()

        cursor = await db.execute(
            """
            SELECT
                id,
                farm_key,
                user_id,
                user_name,
                started_at,
                ends_at
            FROM farm_usage
            WHERE user_id = ?
            AND farm_key = ?
            AND ends_at > ?
            ORDER BY ends_at ASC
            LIMIT 1
            """,
            (user_id, farm_key, timestamp_atual),
        )

        row = await cursor.fetchone()
        await cursor.close()

        if row is None:
            return None

        return FarmUsage(
            id=row["id"],
            farm_key=row["farm_key"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            started_at=row["started_at"],
            ends_at=row["ends_at"],
        )

    async def create(
        self,
        farm_key: str,
        user_id: int,
        user_name: str,
        started_at: int,
        ends_at: int
    ) -> FarmUsage | None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                DELETE FROM farm_usage
                WHERE ends_at <= ?
                """,
                (started_at,),
            )

            cursor = await conn.execute(
                """
                SELECT
                    id,
                    farm_key,
                    user_id,
                    user_name,
                    started_at,
                    ends_at
                FROM farm_usage
                WHERE farm_key = ?
                AND ends_at > ?
                LIMIT 1
                """,
                (farm_key, started_at),
            )

            row = await cursor.fetchone()

            if row is not None:
                return None

            cursor = await conn.execute(
                """
                INSERT INTO farm_usage
                    (
                        farm_key,
                        user_id,
                        user_name,
                        started_at,
                        ends_at
                    )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    farm_key,
                    user_id,
                    user_name,
                    started_at,
                    ends_at,
                ),
            )

            usage_id = cursor.lastrowid

            return FarmUsage(
                id=usage_id,
                farm_key=farm_key,
                user_id=user_id,
                user_name=user_name,
                started_at=started_at,
                ends_at=ends_at,
            )

    async def delete(self, usage_id: int) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                DELETE FROM farm_usage
                WHERE id = ?
                """,
                (usage_id,),
            )

    async def cleanup_expired(self, timestamp_atual: int) -> int:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                DELETE FROM farm_usage
                WHERE ends_at <= ?
                """,
                (timestamp_atual,),
            )

            return cursor.rowcount

    async def get_all_active(
        self,
        timestamp_atual: int
    ) -> list[FarmUsage]:
        db = self.db._require_connection()

        cursor = await db.execute(
            """
            SELECT
                id,
                farm_key,
                user_id,
                user_name,
                started_at,
                ends_at
            FROM farm_usage
            WHERE ends_at > ?
            ORDER BY ends_at ASC
            """,
            (timestamp_atual,),
        )

        rows = await cursor.fetchall()
        await cursor.close()

        return [
            FarmUsage(
                id=row["id"],
                farm_key=row["farm_key"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                started_at=row["started_at"],
                ends_at=row["ends_at"],
            )
            for row in rows
        ]