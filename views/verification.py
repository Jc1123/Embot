import logging

import discord

from config.settings import Settings
from views.tournament import TournamentView


logger = logging.getLogger(__name__)


class VerificationModal(
    discord.ui.Modal,
    title="Painel de Verificação"
):

    minecraft_name = discord.ui.TextInput(
        label="Digite o seu nome no Minecraft:",
        placeholder="...",
        min_length=1,
        max_length=32,
        required=True,
    )

    def __init__(
        self,
        settings: Settings
    ):
        super().__init__()

        self.settings = settings

    async def on_submit(
        self,
        interaction: discord.Interaction
    ) -> None:

        if (
            interaction.guild is None
            or not isinstance(
                interaction.user,
                discord.Member
            )
        ):
            await interaction.response.send_message(
                "❌ Esta ação só pode ser usada "
                "dentro de um servidor.",
                ephemeral=True
            )
            return

        member = interaction.user

        name = self.minecraft_name.value.strip()

        if not name:
            await interaction.response.send_message(
                "❌ O nome não pode ficar vazio.",
                ephemeral=True
            )
            return

        verified = interaction.guild.get_role(
            self.settings.verified_role_id
        )

        unverified = interaction.guild.get_role(
            self.settings.unverified_role_id
        )

        if verified is None:
            await interaction.response.send_message(
                "❌ O cargo 'Verificado' não foi "
                "encontrado. Verifique a configuração "
                "do bot.",
                ephemeral=True
            )
            return

        try:
            await member.edit(
                nick=name,
                reason="Verificação do Minecraft"
            )

        except discord.Forbidden:
            logger.warning(
                "Sem permissão para alterar "
                "o nick de %s.",
                member.id
            )

            await interaction.response.send_message(
                "❌ Não tenho permissão para "
                "alterar seu apelido.",
                ephemeral=True
            )
            return

        except discord.HTTPException:
            logger.exception(
                "Erro HTTP ao alterar nick de %s.",
                member.id
            )

            await interaction.response.send_message(
                "❌ O Discord recusou a alteração "
                "do nick. Tente novamente.",
                ephemeral=True
            )
            return

        try:
            await member.add_roles(
                verified,
                reason="Verificação concluída"
            )

            if (
                unverified
                and unverified in member.roles
            ):
                await member.remove_roles(
                    unverified,
                    reason="Verificação concluída"
                )

        except discord.Forbidden:
            logger.warning(
                "Sem permissão para gerenciar "
                "cargos de verificação de %s.",
                member.id
            )

            await interaction.response.send_message(
                "⚠️ Seu nick foi alterado, mas não "
                "consegui ajustar seus cargos. "
                "Avise a equipe.",
                ephemeral=True
            )
            return

        except discord.HTTPException:
            logger.exception(
                "Erro HTTP ao alterar cargos de %s.",
                member.id
            )

            await interaction.response.send_message(
                "⚠️ Seu nick foi alterado, mas houve "
                "um erro ao ajustar seus cargos.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            (
                f"Tudo pronto, {member.mention}! "
                f"Seu nick foi alterado para "
                f"**{discord.utils.escape_markdown(name)}**.\n\n"
                "👇 **Agora, selecione qual(is) "
                "torneios/cargos você quer participar abaixo:**"
            ),
            view=TournamentView(),
            ephemeral=True
        )