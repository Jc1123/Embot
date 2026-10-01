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
from commands.registration import RegistrationCommands

logger = logging.getLogger(__name__)


class DiscordBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents
        )

        self.settings = settings

        # Banco de dados
        self.database = Database(
            settings.database_path
        )

        self.giveaways = GiveawayRepository(
            self.database
        )

        # Serviço de sorteios
        self.giveaway_service = GiveawayService(
            self.giveaways,
            self
        )

        # Comandos
        self.giveaway_commands = GiveawayCommands(
            self.giveaways,
            self.giveaway_service
        )

        self.verification_commands = VerificationCommands(
            settings
        )

        self.registration_commands = RegistrationCommands(
            settings
        )

        self._persistent_views_registered = False

        # Tratamento global de erros dos slash commands
        self.tree.on_error = self.on_app_command_error

        # Intervalo da verificação automática dos sorteios
        self.check_giveaways.change_interval(
            seconds=settings.giveaway_check_interval
        )

    async def setup_hook(self) -> None:
        """
        Executado pelo discord.py antes do bot ficar pronto.
        Inicializa banco, comandos, views persistentes e tarefas.
        """

        # Inicializa banco de dados
        await self.database.connect()
        await self.database.initialize()

        # Registra comandos
        self.verification_commands.register(
            self.tree
        )

        self.registration_commands.register(
         self.tree
        )

        self.giveaway_commands.register(
            self.tree
        )

        # Registra as views persistentes apenas uma vez
        if not self._persistent_views_registered:
            self.add_view(
                TournamentView()
            )

            self.add_view(
                GiveawayButtonView(
                    self.giveaways
                )
            )

            self._persistent_views_registered = True

        # Sincroniza slash commands
        await self.tree.sync()

        # Inicia verificação automática dos sorteios
        self.check_giveaways.start()

        logger.info(
            "Comandos slash sincronizados com sucesso."
        )

    async def close(self) -> None:
        """
        Fecha corretamente tarefas, banco de dados e conexão com Discord.
        """

        if self.check_giveaways.is_running():
            self.check_giveaways.cancel()

        await self.database.close()

        await super().close()

    async def on_ready(self) -> None:
        """
        Executado quando o bot está conectado e pronto.
        """

        if self.user is None:
            logger.warning(
                "Bot conectado, mas o usuário ainda não está disponível."
            )
            return

        logger.info(
            "Bot conectado como %s (%s).",
            self.user,
            self.user.id
        )

    async def on_member_join(
        self,
        member: discord.Member
    ) -> None:
        """
        Adiciona automaticamente o cargo de não verificado
        quando um membro entra no servidor.
        """

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
        error: discord.app_commands.AppCommandError
    ) -> None:
        """
        Tratamento global de erros dos slash commands.
        """

        logger.error(
            "Erro em slash command: %s",
            error,
            exc_info=(
                type(error),
                error,
                error.__traceback__
            )
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
                "Não foi possível enviar a mensagem "
                "de erro do slash command."
            )

    @tasks.loop(seconds=15)
    async def check_giveaways(self) -> None:
        """
        Verifica periodicamente quais sorteios expiraram.
        """

        now = int(
            discord.utils.utcnow().timestamp()
        )

        try:
            expired = await self.giveaways.get_expired_ids(
                now
            )

            if not expired:
                return

            logger.info(
                "Encontrados %d sorteio(s) expirado(s).",
                len(expired)
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
        """
        Aguarda o bot estar completamente conectado
        antes de iniciar a verificação dos sorteios.
        """

        await self.wait_until_ready()


def main() -> None:
    """
    Ponto de entrada do bot.
    """

    configure_logging()

    try:
        settings = Settings.from_env()

    except Exception:
        logger.exception(
            "Não foi possível carregar as configurações."
        )
        return

    # Verificação segura do token.
    # O token NUNCA é exibido no terminal.
    if not settings.discord_token:
        logger.critical(
            "DISCORD_TOKEN não foi encontrado."
        )

        logger.critical(
            "Verifique se o arquivo .env existe "
            "na pasta do projeto e contém:"
        )

        logger.critical(
            "DISCORD_TOKEN=SEU_TOKEN"
        )

        return

    logger.info(
        "Token do Discord carregado com sucesso."
    )

    bot = DiscordBot(settings)

    try:
        bot.run(
            settings.discord_token,
            log_handler=None
        )

    except discord.LoginFailure:
        logger.critical(
            "Não foi possível autenticar o bot no Discord."
        )

        logger.critical(
            "O DISCORD_TOKEN foi rejeitado pelo Discord."
        )

        logger.critical(
            "Verifique se o token atual foi copiado "
            "corretamente e se não foi regenerado."
        )

    except discord.HTTPException as error:
        logger.critical(
            "Erro HTTP ao iniciar o bot: %s",
            error
        )

    except KeyboardInterrupt:
        logger.info(
            "Bot encerrado manualmente."
        )

    except Exception:
        logger.exception(
            "Erro inesperado durante a execução do bot."
        )


if __name__ == "__main__":
    main()