import logging

import discord

from database.giveaways import GiveawayRepository


logger = logging.getLogger(__name__)


class GiveawayButtonView(
    discord.ui.View
):

    def __init__(
        self,
        repository: GiveawayRepository
    ):
        super().__init__(timeout=None)

        self.repository = repository

    @discord.ui.button(
        label="Participar",
        style=discord.ButtonStyle.primary,
        emoji="🎉",
        custom_id="botao_sorteio_participar",
    )
    async def participate(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:

        await interaction.response.defer(
            ephemeral=True
        )

        message = interaction.message

        if message is None:
            await interaction.followup.send(
                "❌ Não foi possível identificar "
                "o sorteio.",
                ephemeral=True
            )
            return

        result = (
            await self.repository.get_active_by_message(
                message.id
            )
        )

        if result is None:
            await interaction.followup.send(
                "❌ Este sorteio já acabou "
                "ou foi excluído!",
                ephemeral=True
            )
            return

        id_cripto, organizer_id = result

        inserted, total = (
            await self.repository.add_participant(
                id_cripto,
                interaction.user.id
            )
        )

        if not inserted:

            active = await self.repository.get_active(
                id_cripto
            )

            if active is None:
                await interaction.followup.send(
                    "❌ Este sorteio acabou enquanto "
                    "você tentava participar.",
                    ephemeral=True
                )

            else:
                await interaction.followup.send(
                    "Você já está participando "
                    "deste sorteio!",
                    ephemeral=True
                )

            return

        await interaction.followup.send(
            "✅ Sua participação foi registrada "
            "com sucesso!",
            ephemeral=True
        )

        if not message.embeds:
            return

        embed = message.embeds[0]

        try:
            embed.set_field_at(
                0,
                name="",
                value=(
                    f"Organizado por: "
                    f"<@{organizer_id}>\n"
                    f"Número de participantes: "
                    f"{total}\n"
                    "Terminará em breve..."
                ),
                inline=False
            )

            await message.edit(
                embed=embed
            )

        except (
            discord.HTTPException,
            IndexError
        ):
            logger.exception(
                "Não foi possível atualizar "
                "a contagem do sorteio %s.",
                id_cripto
            )