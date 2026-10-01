import discord
from discord import app_commands

from config.settings import Settings
from database.farms import FarmRepository


class FarmCommands:
    def __init__(
        self,
        settings: Settings,
        farms: FarmRepository
    ):
        self.settings = settings
        self.farms = farms

    def register(
        self,
        tree: app_commands.CommandTree
    ) -> None:

        @tree.command(
            name="farms",
            description=(
                "Verifica a disponibilidade das farms."
            ),
        )
        @app_commands.guild_only()
        async def farms(
            interaction: discord.Interaction
        ):

            if (
                interaction.guild is None
                or not isinstance(
                    interaction.user,
                    discord.Member
                )
            ):
                await interaction.response.send_message(
                    "❌ Este comando só pode ser usado "
                    "dentro de um servidor.",
                    ephemeral=True
                )
                return

            now = int(
                discord.utils.utcnow().timestamp()
            )

            # Limpa registros expirados antes da consulta.
            await self.farms.cleanup_expired(
                now
            )

            active = await self.farms.get_all_active(
                now
            )

            active_by_farm = {
                usage.farm_key: usage
                for usage in active
            }

            lines = [
                "# 🌱 Farms existentes",
                ""
            ]

            # -------------------------------------------------
            # Cana
            # -------------------------------------------------

            cana = active_by_farm.get("cana")

            lines.extend([
                "🎋 **Cana de açúcar**",
            ])

            if cana is None:

                lines.extend([
                    "**Status:** 🟢 Disponível",
                    "**Uso registrado por:** Farm livre",
                    "**Data e hora:** Livre",
                ])

            else:

                ends_at = discord.utils.format_dt(
                    discord.utils.snowflake_time(
                        interaction.user.id
                    ),
                    style="f"
                )

                del ends_at

                lines.extend([
                    "**Status:** 🔴 Ocupada",
                    (
                        "**Uso registrado por:** "
                        f"<@{cana.user_id}>"
                    ),
                    (
                        "**Data e hora de término:** "
                        f"<t:{cana.ends_at}:f>"
                    ),
                ])

            lines.append("")

            # -------------------------------------------------
            # Batata
            # -------------------------------------------------

            lines.extend([
                "🥔 **Farm de batata**",
            ])

            if self.settings.farm_batata_indisponivel:

                lines.extend([
                    "**Status:** 🟠 Ocupada, em construção.",
                    "**Uso registrado por:** —",
                    "**Data e hora:** —",
                ])

            else:

                batata = active_by_farm.get("batata")

                if batata is None:

                    lines.extend([
                        "**Status:** 🟢 Disponível",
                        "**Uso registrado por:** Farm livre",
                        "**Data e hora:** Livre",
                    ])

                else:

                    lines.extend([
                        "**Status:** 🔴 Ocupada",
                        (
                            "**Uso registrado por:** "
                            f"<@{batata.user_id}>"
                        ),
                        (
                            "**Data e hora de término:** "
                            f"<t:{batata.ends_at}:f>"
                        ),
                    ])

            await interaction.response.send_message(
                "\n".join(lines),
                ephemeral=True
            )