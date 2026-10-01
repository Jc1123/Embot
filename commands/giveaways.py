import logging
from datetime import datetime, timezone

import discord
from discord import app_commands

from database.giveaways import GiveawayRepository
from services.giveaway_service import GiveawayService
from utils.time import parse_duration


logger = logging.getLogger(__name__)


class GiveawayCommands:
    def __init__(
        self,
        repository: GiveawayRepository,
        service: GiveawayService
    ):
        self.repository = repository
        self.service = service

        self.group = app_commands.Group(
            name="sorteio",
            description=(
                "Gerencia os sorteios do servidor"
            ),
            default_permissions=discord.Permissions(
                administrator=True
            ),
        )

    @staticmethod
    def _is_admin(
        interaction: discord.Interaction
    ) -> bool:

        return (
            interaction.guild is not None
            and isinstance(
                interaction.user,
                discord.Member
            )
            and interaction.user.guild_permissions.administrator
        )

    def register(
        self,
        tree: app_commands.CommandTree
    ) -> None:

        @self.group.command(
            name="criar",
            description=(
                "Cria um novo sorteio e "
                "persiste na base de dados."
            )
        )
        @app_commands.describe(
            title="Título",
            desc="Descrição",
            time="Tempo (ex: 30s, 10m, 2h)",
            ganhadores="Quantidade de vencedores",
        )
        @app_commands.guild_only()
        async def criar(
            interaction: discord.Interaction,
            title: str,
            desc: str,
            time: str,
            ganhadores: int,
        ):

            if not self._is_admin(interaction):
                await interaction.response.send_message(
                    "❌ Apenas administradores "
                    "podem usar este comando.",
                    ephemeral=True
                )
                return

            if interaction.channel is None:
                await interaction.response.send_message(
                    "❌ Não foi possível identificar o canal.",
                    ephemeral=True
                )
                return

            title = title.strip()
            desc = desc.strip()
            time = time.strip()

            if not title or len(title) > 256:
                await interaction.response.send_message(
                    "❌ O título deve ter entre "
                    "1 e 256 caracteres.",
                    ephemeral=True
                )
                return

            if not desc or len(desc) > 4096:
                await interaction.response.send_message(
                    "❌ A descrição deve ter entre "
                    "1 e 4096 caracteres.",
                    ephemeral=True
                )
                return

            if not 1 <= ganhadores <= 100:
                await interaction.response.send_message(
                    "❌ A quantidade de ganhadores "
                    "deve estar entre 1 e 100.",
                    ephemeral=True
                )
                return

            seconds = parse_duration(time)

            if seconds is None or seconds <= 0:
                await interaction.response.send_message(
                    "❌ Tempo inválido! Exemplos: "
                    "`30s`, `10m`, `2h`, `1d`.",
                    ephemeral=True
                )
                return

            timestamp_end = (
                int(
                    datetime.now(
                        timezone.utc
                    ).timestamp()
                )
                + seconds
            )

            try:
                id_cripto = (
                    await self.service.create_message(
                        channel=interaction.channel,
                        title=title,
                        description=desc,
                        organizer_id=interaction.user.id,
                        duration_end=timestamp_end,
                        winners=ganhadores,
                    )
                )

            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ O bot não possui permissão "
                    "para enviar a mensagem do sorteio "
                    "neste canal.",
                    ephemeral=True
                )
                return

            except discord.HTTPException:
                logger.exception(
                    "Falha HTTP ao criar sorteio."
                )

                await interaction.response.send_message(
                    "❌ O Discord recusou a criação "
                    "do sorteio. Tente novamente.",
                    ephemeral=True
                )
                return

            except Exception:
                logger.exception(
                    "Erro inesperado ao criar sorteio."
                )

                await interaction.response.send_message(
                    "❌ Ocorreu um erro interno "
                    "ao criar o sorteio.",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"🎉 Sorteio criado com sucesso! "
                f"ID: `{id_cripto}`",
                ephemeral=True
            )

        @self.group.command(
            name="excluir",
            description=(
                "Cancela e exclui um sorteio em andamento."
            )
        )
        @app_commands.describe(
            id="ID do sorteio"
        )
        @app_commands.guild_only()
        async def excluir(
            interaction: discord.Interaction,
            id: str
        ):

            if not self._is_admin(interaction):
                await interaction.response.send_message(
                    "❌ Apenas administradores "
                    "podem usar este comando.",
                    ephemeral=True
                )
                return

            id_clean = id.strip()

            giveaway = await self.repository.get_active(
                id_clean
            )

            if giveaway is None:
                await interaction.response.send_message(
                    "❌ Nenhum sorteio ativo encontrado "
                    "com esse ID.",
                    ephemeral=True
                )
                return

            await self.repository.deactivate(
                id_clean
            )

            channel = (
                interaction.guild.get_channel(
                    giveaway.canal_id
                )
                if interaction.guild
                else None
            )

            if channel:
                try:
                    message = await channel.fetch_message(
                        giveaway.mensagem_id
                    )

                    await message.delete()

                except discord.NotFound:
                    logger.warning(
                        "Mensagem do sorteio %s "
                        "já havia sido apagada.",
                        id_clean
                    )

                except discord.Forbidden:
                    logger.warning(
                        "Sem permissão para apagar "
                        "a mensagem do sorteio %s.",
                        id_clean
                    )

                except discord.HTTPException:
                    logger.exception(
                        "Erro HTTP ao excluir sorteio %s.",
                        id_clean
                    )

            await interaction.response.send_message(
                f"🗑️ O sorteio `{id_clean}` foi "
                "cancelado e excluído com sucesso.",
                ephemeral=True
            )

        @self.group.command(
            name="finalizar",
            description=(
                "Finaliza antecipadamente um sorteio."
            )
        )
        @app_commands.describe(
            id="ID do sorteio"
        )
        @app_commands.guild_only()
        async def finalizar(
            interaction: discord.Interaction,
            id: str
        ):

            if not self._is_admin(interaction):
                await interaction.response.send_message(
                    "❌ Apenas administradores "
                    "podem usar este comando.",
                    ephemeral=True
                )
                return

            id_clean = id.strip()

            if (
                await self.repository.get_active(
                    id_clean
                )
                is None
            ):
                await interaction.response.send_message(
                    "❌ Nenhum sorteio ativo encontrado "
                    "com esse ID.",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"🏁 Finalizando o sorteio "
                f"`{id_clean}`...",
                ephemeral=True
            )

            try:
                finalized = await self.service.finalize(
                    id_clean
                )

                if not finalized:
                    logger.info(
                        "Sorteio %s já havia sido finalizado.",
                        id_clean
                    )

            except Exception:
                logger.exception(
                    "Erro inesperado ao finalizar "
                    "sorteio %s.",
                    id_clean
                )

        tree.add_command(
            self.group
        )