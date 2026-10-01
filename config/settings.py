import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    database_path: str = "bot_database.db"
    giveaway_check_interval: int = 15

    verified_role_id: int = 1546935292450312202
    unverified_role_id: int = 1547044422913490964

    farm_channel_id: int = 1546568509402775716

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN")

        if not token:
            raise RuntimeError(
                "A variável de ambiente DISCORD_TOKEN "
                "não foi definida."
            )

        return cls(
            discord_token=token,
            database_path=os.getenv(
                "DATABASE_PATH",
                "bot_database.db"
            ),
            giveaway_check_interval=max(
                5,
                int(
                    os.getenv(
                        "GIVEAWAY_CHECK_INTERVAL",
                        "15"
                    )
                )
            ),
        )


TOURNAMENT_ROLES: dict[str, int] = {
    "Alquimista": 1541613339942330499,
    "Pescador": 1541630361405231266,
    "Britadeira": 1541613312050200616,
    "Escavador": 1541626898663346237,
    "Builder": 1541612082569543784,
    "Fazendeiro": 1541613451909267497,
    "Slayer": 1541630332087050320,
    "Recruta": 1541613288096407642,
}


TOURNAMENT_OPTIONS = (
    (
        "Alquimista",
        "🧪",
        "Torneio de Alquimista"
    ),
    (
        "Pescador",
        "🐟",
        "Torneio de Pesca"
    ),
    (
        "Britadeira",
        "⛏️",
        "Torneio Britadeira"
    ),
    (
        "Escavador",
        "🧹",
        "Torneio Escavador"
    ),
    (
        "Builder",
        "✂️",
        "Cargo de Builder"
    ),
    (
        "Fazendeiro",
        "🌱",
        "Torneio Farmer"
    ),
    (
        "Slayer",
        "⚔️",
        "Torneio Slayer"
    ),
    (
        "Recruta",
        "❌",
        "Sem cargos no torneio"
    ),
)