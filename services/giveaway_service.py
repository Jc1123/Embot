import logging
import random
from datetime import datetime, timezone

import discord

from database.giveaways import (
    GiveawayRepository,
)
from views.giveaway import GiveawayButtonView
from utils.embeds import giveaway_embed


logger = logging.getLogger(__name__)


class GiveawayService:

    def __init__(
        self,
        repository: GiveawayRepository,
        client: discord.Client
    ):
        self.repository = repository
        self.client = client

    async def create_message(
        self,
        *,
        channel: discord.abc.Messageable,
        title: str,
        description: str,
        organizer_id: int,
        duration_end: int,
        winners: int,
    ) -> str:

        id_cripto = (
            await self.repository.create(
                titulo=title,
                descricao=description,
                timestamp_termino=duration_end,
                organizador_id=organizer_id,
                ganhadores=winners,
                canal_id=channel.id,
            )
        )

        try:
            embed = giveaway_embed(
                title,
                description,
                organizer_id,
                0,
                (
                    "Começado em • "
                    f"{datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')}"
                    ".astimezone()"
                    ".strftime('%d/%m/%Y %H:%M')}"
                    f" | ID: {id_cripto}"
                ),
                discord.Color.from_rgb(
                    235,
                    64,
                    52
                ),
            )

            message = await channel.send(
                embed=embed,
                view=GiveawayButtonView(
                    self.repository
                )
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):
            await self.repository.deactivate(
                id_cripto
            )
            raise

        try:
            updated = (
                await self.repository.set_message_id(
                    id_cripto,
                    message.id
                )
            )

            if not updated:
                raise RuntimeError(
                    "O sorteio foi desativado antes "
                    "de registrar a mensagem."
                )

        except Exception:

            try:
                await message.delete()

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):
                logger.exception(
                    "Não foi possível remover a mensagem "
                    "órfã do sorteio %s.",
                    id_cripto
                )

            await self.repository.deactivate(
                id_cripto
            )

            raise

        return id_cripto

    async def finalize(
        self,
        id_cripto: str
    ) -> bool:

        result = (
            await self.repository
            .finalize_and_get_data(
                id_cripto
            )
        )

        if result is None:
            return False

        giveaway, participants = result

        channel = self.client.get_channel(
            giveaway.canal_id
        )

        if channel is None:
            logger.error(
                "Canal %s não encontrado para "
                "o sorteio %s.",
                giveaway.canal_id,
                id_cripto
            )
            return True

        message = None

        try:
            message = await channel.fetch_message(
                giveaway.mensagem_id
            )

        except discord.NotFound:
            logger.warning(
                "Mensagem do sorteio %s "
                "já foi apagada.",
                id_cripto
            )

        except discord.Forbidden:
            logger.error(
                "Sem permissão para buscar "
                "a mensagem do sorteio %s.",
                id_cripto
            )

        except discord.HTTPException:
            logger.exception(
                "Erro HTTP ao buscar mensagem "
                "do sorteio %s.",
                id_cripto
            )

        minimum = (
            3
            if giveaway.ganhadores == 1
            else giveaway.ganhadores * 2
        )

        embed = discord.Embed(
            title=giveaway.titulo,
            description=giveaway.descricao,
            color=discord.Color.from_rgb(
                52,
                235,
                119
            ),
        )

        view = GiveawayButtonView(
            self.repository
        )

        for child in view.children:
            if isinstance(
                child,
                discord.ui.Button
            ):
                child.disabled = True

        finished_at = (
            datetime.now(timezone.utc)
            .astimezone()
            .strftime("%d/%m/%Y %H:%M")
        )

        if len(participants) >= minimum:

            winner_ids = random.sample(
                participants,
                min(
                    giveaway.ganhadores,
                    len(participants)
                )
            )

            mentions = ", ".join(
                f"<@{uid}>"
                for uid in winner_ids
            )

            embed.add_field(
                name="",
                value=(
                    f"Vencedores: {mentions}\n"
                    f"Organizado por: "
                    f"<@{giveaway.organizador_id}>\n"
                    f"Número de participantes: "
                    f"{len(participants)}"
                ),
                inline=False
            )

            embed.set_footer(
                text=(
                    f"Terminado em • {finished_at}"
                    f" | ID: {id_cripto}"
                )
            )

            if message:

                try:
                    await message.edit(
                        embed=embed,
                        view=view
                    )

                except discord.HTTPException:
                    logger.exception(
                        "Erro ao atualizar mensagem "
                        "final do sorteio %s.",
                        id_cripto
                    )

            try:
                await channel.send(
                    "Sorteio finalizado. "
                    f"Parabéns aos vencedores! 🎉 "
                    f"({mentions})"
                )

            except discord.HTTPException:
                logger.exception(
                    "Erro ao anunciar vencedores "
                    "do sorteio %s.",
                    id_cripto
                )

        else:

            embed.color = (
                discord.Color.from_rgb(
                    200,
                    200,
                    200
                )
            )

            embed.add_field(
                name="",
                value=(
                    "Vencedores: **Cancelado "
                    "por falta de participantes**\n"
                    f"Organizado por: "
                    f"<@{giveaway.organizador_id}>\n"
                    f"Número de participantes: "
                    f"{len(participants)}"
                ),
                inline=False
            )

            embed.set_footer(
                text=(
                    f"Terminado em • {finished_at}"
                    f" | ID: {id_cripto}"
                )
            )

            if message:

                try:
                    await message.edit(
                        embed=embed,
                        view=view
                    )

                except discord.HTTPException:
                    logger.exception(
                        "Erro ao atualizar "
                        "cancelamento do sorteio %s.",
                        id_cripto
                    )

            try:
                await channel.send(
                    "Sorteio finalizado, mas não atingiu "
                    "o número mínimo de participantes "
                    f"(mínimo necessário: {minimum})."
                )

            except discord.HTTPException:
                logger.exception(
                    "Erro ao anunciar cancelamento "
                    "do sorteio %s.",
                    id_cripto
                )

        return True