import discord
from discord import app_commands

from config.settings import Settings
from database.farms import FarmRepository
from views.registration import FarmSelectionView


class RegistrationCommands:
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
            name="registrar",
            description=(
                "Registra o uso de uma farm."
            ),
        )
        @app_commands.guild_only()
        async def registrar(
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

            await interaction.response.send_message(
                "🌱 **Selecione a farm que deseja registrar:**",
                view=FarmSelectionView(
                    self.settings,
                    self.farms,
                    interaction.user
                ),
                ephemeral=True
            )