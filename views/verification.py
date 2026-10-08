import logging

import discord

from config.settings import Settings, TOURNAMENT_ROLES
from services.linking_service import LinkingService
from views.tournament import TournamentView


logger = logging.getLogger(__name__)


class VerificationModal(
    discord.ui.Modal,
    title="🔗 Vincular Conta"
):

    verification_code = discord.ui.TextInput(
        label="Código de verificação",
        placeholder="Digite o código gerado no Minecraft",
        min_length=8,
        max_length=8,
        required=True,
    )

    def __init__(
        self,
        settings: Settings,
        linking_service: LinkingService
    ):
        super().__init__()

        self.settings = settings
        self.linking_service = linking_service

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

        code = (
            self.verification_code.value
            .strip()
            .upper()
        )

        if len(code) != 8:
            await interaction.response.send_message(
                "❌ O código deve possuir exatamente "
                "8 caracteres.",
                ephemeral=True
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            link = await self.linking_service.get_link(
                code
            )

        except Exception:
            logger.exception(
                "Erro ao consultar código %s.",
                code
            )

            await interaction.followup.send(
                (
                    "❌ Não foi possível conectar ao "
                    "sistema de verificação do Minecraft. "
                    "Tente novamente em alguns instantes."
                ),
                ephemeral=True
            )
            return

        if link is None:
            await interaction.followup.send(
                (
                    "❌ Código inválido ou expirado.\n\n"
                    "Gere um novo código usando "
                    "`/verificar` no Minecraft."
                ),
                ephemeral=True
            )
            return

        verified_role = interaction.guild.get_role(
            self.settings.verified_role_id
        )

        unverified_role = interaction.guild.get_role(
            self.settings.unverified_role_id
        )

        if verified_role is None:
            logger.error(
                "Cargo Verificado não encontrado."
            )

            await interaction.followup.send(
                (
                    "❌ O cargo **Verificado** não foi "
                    "encontrado. Avise a equipe."
                ),
                ephemeral=True
            )
            return

        tournament_role_id = TOURNAMENT_ROLES.get(
            link.cargo
        )

        tournament_role = None

        if tournament_role_id is not None:
            tournament_role = interaction.guild.get_role(
                tournament_role_id
            )

        try:
            await member.edit(
                nick=link.minecraft_nick,
                reason="Vinculação da conta do Minecraft"
            )

        except discord.Forbidden:
            logger.warning(
                "Sem permissão para alterar "
                "o nick de %s.",
                member.id
            )

            await interaction.followup.send(
                (
                    "❌ Não tenho permissão para "
                    "alterar seu apelido."
                ),
                ephemeral=True
            )
            return

        except discord.HTTPException:
            logger.exception(
                "Erro HTTP ao alterar nick de %s.",
                member.id
            )

            await interaction.followup.send(
                (
                    "❌ O Discord recusou a alteração "
                    "do nick. Tente novamente."
                ),
                ephemeral=True
            )
            return

        try:
            await member.add_roles(
                verified_role,
                reason="Verificação concluída"
            )

            if (
                unverified_role
                and unverified_role in member.roles
            ):
                await member.remove_roles(
                    unverified_role,
                    reason="Verificação concluída"
                )

            if (
                tournament_role
                and tournament_role not in member.roles
            ):
                await member.add_roles(
                    tournament_role,
                    reason=(
                        "Cargo do Minecraft "
                        "vinculado automaticamente"
                    )
                )

        except discord.Forbidden:
            logger.warning(
                "Sem permissão para gerenciar "
                "cargos de %s.",
                member.id
            )

            await interaction.followup.send(
                (
                    "⚠️ Seu nick foi alterado, mas não "
                    "consegui ajustar todos os cargos. "
                    "Avise a equipe."
                ),
                ephemeral=True
            )
            return

        except discord.HTTPException:
            logger.exception(
                "Erro HTTP ao alterar cargos de %s.",
                member.id
            )

            await interaction.followup.send(
                (
                    "⚠️ Seu nick foi alterado, mas houve "
                    "um erro ao ajustar os cargos."
                ),
                ephemeral=True
            )
            return

        try:
            consumed = await self.linking_service.consume_link(
                code
            )

        except Exception:
            logger.exception(
                "Erro ao consumir código %s.",
                code
            )

            await interaction.followup.send(
                (
                    "⚠️ Sua conta foi atualizada no Discord, "
                    "mas não consegui finalizar o consumo "
                    "do código. Avise a equipe."
                ),
                ephemeral=True
            )
            return

        if consumed is None:
            logger.error(
                "Código %s deixou de estar disponível "
                "antes do consumo.",
                code
            )

            await interaction.followup.send(
                (
                    "⚠️ A conta foi atualizada, mas o código "
                    "não pôde ser consumido. Avise a equipe."
                ),
                ephemeral=True
            )
            return

        role_message = ""

        if tournament_role:
            role_message = (
                f"\n🎖️ Cargo vinculado: "
                f"**{link.cargo}**"
            )

        else:
            role_message = (
                f"\nℹ️ Cargo do Minecraft: "
                f"**{link.cargo}**"
            )

        await interaction.followup.send(
            (
                f"✅ **Conta vinculada com sucesso!**\n\n"
                f"🎮 Minecraft: "
                f"**{discord.utils.escape_markdown(link.minecraft_nick)}**\n"
                f"🏷️ Cargo: **{discord.utils.escape_markdown(link.cargo)}**"
                f"{role_message}\n\n"
                "👇 **Agora, selecione qual(is) "
                "torneios/cargos você quer participar abaixo:**"
            ),
            view=TournamentView(),
            ephemeral=True
        )