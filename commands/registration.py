import discord
from discord import app_commands

from config.settings import Settings
from database.farms import FarmRepository
from views.registration import FarmSelectionView


FARM_CHOICES = [
    app_commands.Choice(name="Cana de açúcar", value="cana"),
    app_commands.Choice(name="Batata", value="batata"),
]


class RegistrationCommands:
    def __init__(
        self,
        settings: Settings,
        farms: FarmRepository
    ):
        self.settings = settings
        self.farms = farms

    def register(self, tree: app_commands.CommandTree) -> None:
        registrar = app_commands.Group(
            name="registrar",
            description="Comandos para registro de farms.",
        )

        @registrar.command(
            name="usar",
            description="Registra o uso de uma farm.",
        )
        async def registrar_usar(
            interaction: discord.Interaction
        ):
            if (
                interaction.guild is None
                or not isinstance(interaction.user, discord.Member)
            ):
                await interaction.response.send_message(
                    "❌ Este comando só pode ser usado dentro de um servidor.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                "🌱 **Selecione a farm que deseja registrar:**",
                view=FarmSelectionView(
                    self.settings,
                    self.farms,
                    interaction.user,
                ),
                ephemeral=True,
            )

        @registrar.command(
            name="excluir",
            description="Exclui seu registro atual de uma farm.",
        )
        @app_commands.describe(
            farm="A farm cujo registro você deseja excluir."
        )
        @app_commands.choices(farm=FARM_CHOICES)
        async def registrar_excluir(
            interaction: discord.Interaction,
            farm: app_commands.Choice[str],
        ):
            if (
                interaction.guild is None
                or not isinstance(interaction.user, discord.Member)
            ):
                await interaction.response.send_message(
                    "❌ Este comando só pode ser usado dentro de um servidor.",
                    ephemeral=True,
                )
                return

            now = int(discord.utils.utcnow().timestamp())

            await self.farms.cleanup_expired(now)

            usage = await self.farms.get_active_by_user_and_farm(
                user_id=interaction.user.id,
                farm_key=farm.value,
                timestamp_atual=now,
            )

            if usage is None:
                await interaction.response.send_message(
                    "❌ A farm não tem registros de uso atual.",
                    ephemeral=True,
                )
                return

            await self.farms.delete(usage.id)

            await interaction.response.send_message(
                (
                    f"✅ Seu registro da farm **{farm.name}** foi excluído "
                    "com sucesso."
                ),
                ephemeral=True,
            )

        tree.add_command(registrar)