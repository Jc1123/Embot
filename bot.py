import logging

import discord
from discord.ext import commands, tasks

from commands.giveaways import GiveawayCommands
from commands.verification import VerificationCommands
from config.logging_config import configure_logging
from config.settings import Settings
from database.connection import Database
from database.giveaways import GiveawayRepository
from services.giveaway_service import GiveawayService
from views.giveaway import GiveawayButtonView
from views.tournament import TournamentView

logger = logging.getLogger(__name__)


class DiscordBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.database = Database(settings.database_path)

        self.giveaways = GiveawayRepository(self.database)

        self.giveaway_service = GiveawayService(
            self.giveaways,
            self
        )

        self.giveaway_commands = GiveawayCommands(
            self.giveaways,
            self.giveaway_service
        )

        self.verification_commands = VerificationCommands(
            settings
        )

        self._persistent_views_registered = False

        self.tree.on_error = self.on_app_command_error

        self.check_giveaways.change_interval(
            seconds=settings.giveaway_check_interval
        )

    async def setup_hook(self) -> None:
        await self.database.connect()
        await self.database.initialize()

        self.verification_commands.register(self.tree)
        self.giveaway_commands.register(self.tree)

        if not self._persistent_views_registered:
            self.add_view(TournamentView())
            self.add_view(
                GiveawayButtonView(self.giveaways)
            )

            self._persistent_views_registered = True

        await self.tree.sync()

        self.check_giveaways.start()

        logger.info(
            "Comandos slash sincronizados com sucesso."
        )

    async def close(self) -> None:
        if self.check_giveaways.is_running():
            self.check_giveaways.cancel()

        await self.database.close()

        await super().close()

    async def on_member_join(
        self,
        member: discord.Member
    ) -> None:

        role = member.guild.get_role(
            self.settings.unverified_role_id
        )

        if role is None:
            logger.warning(
                "Cargo não verificado não encontrado no servidor %s.",
                member.guild.id
            )
            return

        try:
            await member.add_roles(
                role,
                reason="Entrada no servidor"
            )

            logger.info(
                "Cargo não verificado adicionado a %s (%s).",
                member,
                member.id
            )

        except discord.Forbidden:
            logger.warning(
                "Sem permissão para dar cargo não verificado a %s.",
                member.id
            )

        except discord.HTTPException:
            logger.exception(
                "Erro HTTP ao adicionar cargo não verificado a %s.",
                member.id
            )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:

        logger.error(
            "Erro em slash command: %s",
            error,
            exc_info=(
                type(error),
                error,
                error.__traceback__
            ),
        )

        message = (
            "❌ Ocorreu um erro ao executar o comando."
        )

        if isinstance(
            error,
            discord.app_commands.CommandOnCooldown
        ):
            message = (
                f"⏳ Aguarde "
                f"{error.retry_after:.1f}s antes de tentar novamente."
            )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    message,
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    message,
                    ephemeral=True
                )

        except discord.HTTPException:
            logger.exception(
                "Não foi possível enviar a mensagem de erro "
                "do slash command."
            )

    @tasks.loop(seconds=15)
    async def check_giveaways(self) -> None:
        now = int(
            discord.utils.utcnow().timestamp()
        )

        try:
            expired = await self.giveaways.get_expired_ids(
                now
            )

            for id_cripto in expired:
                try:
                    await self.giveaway_service.finalize(
                        id_cripto
                    )

                except Exception:
                    logger.exception(
                        "Erro ao finalizar automaticamente "
                        "o sorteio %s.",
                        id_cripto
                    )

        except Exception:
            logger.exception(
                "Erro na rotina de verificação dos sorteios."
            )

    @check_giveaways.before_loop
    async def before_check_giveaways(self) -> None:
        await self.wait_until_ready()


def main() -> None:
    configure_logging()

    settings = Settings.from_env()

    bot = DiscordBot(settings)

    @bot.event
    async def on_ready() -> None:
        logger.info(
            "Bot conectado como %s (%s).",
            bot.user,
            bot.user.id if bot.user else "sem ID"
        )

    try:
        bot.run(
            settings.discord_token,
            log_handler=None
        )

    except KeyboardInterrupt:
        logger.info(
            "Bot encerrado manualmente."
        )


if __name__ == "__main__":
    main()