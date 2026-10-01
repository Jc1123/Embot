import logging

import discord

from config.settings import (
    TOURNAMENT_OPTIONS,
    TOURNAMENT_ROLES,
)


logger = logging.getLogger(__name__)


class TournamentSelect(discord.ui.Select):
    def __init__(self):

        options = [
            discord.SelectOption(
                label=name,
                emoji=emoji,
                description=description
            )
            for name, emoji, description
            in TOURNAMENT_OPTIONS
        ]

        super().__init__(
            custom_id="menu_torneio_selecionar",
            placeholder=(
                "Selecione seu(s) "
                "cargo(s) do torneio..."
            ),
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ) -> None:

        await interaction.response.defer(
            ephemeral=True
        )

        if (
            interaction.guild is None
            or not isinstance(
                interaction.user,
                discord.Member
            )
        ):
            await interaction.followup.send(
                "❌ Esta ação só pode ser usada "
                "dentro de um servidor.",
                ephemeral=True
            )
            return

        member = interaction.user

        roles = []
        missing = []

        for role_name in self.values:

            role_id = TOURNAMENT_ROLES.get(
                role_name
            )

            role = (
                interaction.guild.get_role(
                    role_id
                )
                if role_id
                else None
            )

            if role is None:
                missing.append(
                    role_name
                )
            else:
                roles.append(role)

        if roles:

            try:
                await member.add_roles(
                    *roles,
                    reason=(
                        "Seleção de "
                        "cargos de torneio"
                    )
                )

            except discord.Forbidden:
                logger.warning(
                    "Sem permissão para adicionar "
                    "cargos a %s (%s).",
                    member,
                    member.id
                )

                await interaction.followup.send(
                    "❌ O bot não possui permissão "
                    "para dar esses cargos.",
                    ephemeral=True
                )
                return

            except discord.HTTPException:
                logger.exception(
                    "Erro HTTP ao adicionar cargos "
                    "de torneio a %s.",
                    member.id
                )

                await interaction.followup.send(
                    "❌ O Discord recusou a alteração "
                    "dos cargos. Tente novamente.",
                    ephemeral=True
                )
                return

        parts = []

        if roles:
            parts.append(
                "✅ Você recebeu: **"
                + ", ".join(
                    role.name
                    for role in roles
                )
                + "**"
            )

        if missing:
            parts.append(
                "⚠️ Não encontrei: "
                + ", ".join(missing)
                + ". Avise um Líder!"
            )

        await interaction.followup.send(
            "\n".join(parts)
            or "Nenhum cargo foi alterado.",
            ephemeral=True
        )


class TournamentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            TournamentSelect()
        )