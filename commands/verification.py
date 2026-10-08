import discord
from discord import app_commands

from config.settings import Settings
from services.linking_service import LinkingService
from views.verification import VerificationModal


class VerificationCommands:
    def __init__(
        self,
        settings: Settings,
        linking_service: LinkingService
    ):
        self.settings = settings
        self.linking_service = linking_service

    def register(
        self,
        tree: app_commands.CommandTree
    ) -> None:

        @tree.command(
            name="verificar",
            description=(
                "Vincula sua conta usando o código "
                "gerado no Minecraft."
            ),
        )
        @app_commands.guild_only()
        async def verificar(
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

            role = interaction.guild.get_role(
                self.settings.verified_role_id
            )

            if (
                role
                and role in interaction.user.roles
            ):
                await interaction.response.send_message(
                    "Você já está verificado no servidor.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(
                VerificationModal(
                    self.settings,
                    self.linking_service
                )
            )