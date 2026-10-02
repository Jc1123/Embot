import discord
from discord import app_commands

from database.farms import FarmRepository


FARM_CHOICES = [
    app_commands.Choice(name="Cana de açúcar", value="cana"),
    app_commands.Choice(name="Batata", value="batata"),
]


FARM_NAMES = {
    "cana": "Cana de açúcar",
    "batata": "Batata",
}


class AdminCommands:
    def __init__(self, farms: FarmRepository):
        self.farms = farms

    def register(self, tree: app_commands.CommandTree) -> None:
        excluir = app_commands.Group(
            name="excluir",
            description="Comandos administrativos.",
        )

        @excluir.command(
            name="registro",
            description="Exclui o registro atual de uma farm.",
        )
        @app_commands.describe(
            farm="A farm cujo registro será excluído."
        )
        @app_commands.choices(farm=FARM_CHOICES)
        @app_commands.checks.has_permissions(administrator=True)
        async def excluir_registro(
            interaction: discord.Interaction,
            farm: app_commands.Choice[str],
        ):
            if interaction.guild is None:
                await interaction.response.send_message(
                    "❌ Este comando só pode ser usado dentro de um servidor.",
                    ephemeral=True,
                )
                return

            now = int(discord.utils.utcnow().timestamp())

            await self.farms.cleanup_expired(now)

            usage = await self.farms.get_active(
                farm.value,
                now,
            )

            if usage is None:
                await interaction.response.send_message(
                    "❌ A farm não tem registros de uso atual.",
                    ephemeral=True,
                )
                return

            farm_name = FARM_NAMES.get(
                farm.value,
                farm.name,
            )

            await self.farms.delete(usage.id)

            await interaction.response.send_message(
                (
                    f"✅ O registro da farm **{farm_name}** foi excluído.\n\n"
                    f"**Jogador:** <@{usage.user_id}>\n"
                    f"**Nick:** `{usage.user_name}`"
                ),
                ephemeral=True,
            )

        @excluir_registro.error
        async def excluir_registro_error(
            interaction: discord.Interaction,
            error: app_commands.AppCommandError,
        ):
            if isinstance(
                error,
                app_commands.errors.MissingPermissions
            ):
                message = (
                    "❌ Você precisa ter a permissão de "
                    "**Administrador** para usar este comando."
                )
            else:
                message = (
                    "❌ Ocorreu um erro ao executar o comando."
                )

            if interaction.response.is_done():
                await interaction.followup.send(
                    message,
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )

        tree.add_command(excluir)