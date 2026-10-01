import logging
import re
from datetime import datetime

import discord

from config.settings import Settings


logger = logging.getLogger(__name__)


FARM_OPTIONS = {
    "cana": "🎋 Farm de cana de açúcar",
    "batata": "🥔 Farm de batata",
}


def format_date_time(value: str) -> str | None:
    """
    Converte diferentes formatos de data/hora para:

    DD/MM/YY HH:MM

    Exemplos aceitos:
        0110261536
        011026 1536
        01/10/26 15:36
        01/10/26 15:36

    Retorna None caso o valor seja inválido.
    """

    # Remove espaços nas extremidades
    value = value.strip()

    if not value:
        return None

    # Remove espaços extras
    value = re.sub(r"\s+", " ", value)

    # ---------------------------------------------------------
    # Formato já completo:
    # DD/MM/YY HH:MM
    # ---------------------------------------------------------
    match = re.fullmatch(
        r"(\d{2})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})",
        value
    )

    if match:
        day, month, year, hour, minute = match.groups()

    else:
        # -----------------------------------------------------
        # Remove caracteres que não sejam números
        #
        # Assim:
        # 01/10/26 15:36
        # 01-10-26 15-36
        # 011026 1536
        #
        # viram:
        # 0110261536
        # -----------------------------------------------------
        numbers = re.sub(r"\D", "", value)

        # Precisamos de exatamente 10 números:
        # DDMMYYHHMM
        if len(numbers) != 10:
            return None

        day = numbers[0:2]
        month = numbers[2:4]
        year = numbers[4:6]
        hour = numbers[6:8]
        minute = numbers[8:10]

    # ---------------------------------------------------------
    # Validação real da data e hora
    # ---------------------------------------------------------
    try:
        date = datetime.strptime(
            f"{day}/{month}/{year} {hour}:{minute}",
            "%d/%m/%y %H:%M"
        )

    except ValueError:
        return None

    return date.strftime("%d/%m/%y %H:%M")


class RegistrationModal(
    discord.ui.Modal,
    title="Registrar uso de farm"
):

    minecraft_name = discord.ui.TextInput(
        label="Nick:",
        placeholder="Insira seu nick no Minecraft",
        min_length=1,
        max_length=32,
        required=True,
    )

    date_time = discord.ui.TextInput(
        label="Data e hora:",
        placeholder="Ex: 0110261536",
        min_length=10,
        max_length=19,
        required=True,
    )

    def __init__(
        self,
        settings: Settings,
        member: discord.Member,
        farm: str
    ):
        super().__init__()

        self.settings = settings
        self.member = member
        self.farm = farm

        # Preenche automaticamente com o nome atual
        # do usuário no Discord.
        self.minecraft_name.default = (
            member.display_name[:32]
        )

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

        name = self.minecraft_name.value.strip()
        date_time_input = self.date_time.value.strip()

        # -----------------------------------------------------
        # Validação do nick
        # -----------------------------------------------------
        if not name:
            await interaction.response.send_message(
                "❌ O nick não pode ficar vazio.",
                ephemeral=True
            )
            return

        # -----------------------------------------------------
        # Formatação e validação da data/hora
        # -----------------------------------------------------
        date_time = format_date_time(
            date_time_input
        )

        if date_time is None:
            await interaction.response.send_message(
                (
                    "❌ **Data e hora inválidas.**\n\n"
                    "Digite no formato:\n"
                    "`DDMMYYHHMM`\n\n"
                    "Exemplo:\n"
                    "`0110261536` → `01/10/26 15:36`\n\n"
                    "Também é possível usar:\n"
                    "`01/10/26 15:36`"
                ),
                ephemeral=True
            )
            return

        # -----------------------------------------------------
        # Procura o canal de registros
        # -----------------------------------------------------
        channel = interaction.guild.get_channel(
            self.settings.farm_channel_id
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ O canal de registros de farm "
                "não foi encontrado. Avise a equipe.",
                ephemeral=True
            )

            logger.warning(
                "Canal de farms não encontrado: %s",
                self.settings.farm_channel_id
            )

            return

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            await interaction.response.send_message(
                "❌ O canal configurado para os registros "
                "de farm não é um canal de texto válido.",
                ephemeral=True
            )
            return

        # -----------------------------------------------------
        # Mensagem pública do registro
        # -----------------------------------------------------
        message = (
            "# Uso de farm registrada\n"
            f"**Membro:** {self.member.mention}\n"
            f"**Farm utilizada:** {self.farm}\n"
            f"**Horário:** {date_time}\n\n"
            "A Farm será utilizada pelo jogador no horário acima. "
            "Caso não seja você que registrou a farm, "
            "**não utilize a farm**."
        )

        try:
            await channel.send(message)

        except discord.Forbidden:
            logger.warning(
                "Sem permissão para enviar mensagens "
                "no canal de farms %s.",
                channel.id
            )

            await interaction.response.send_message(
                "❌ Não tenho permissão para enviar "
                "mensagens no canal de farms.",
                ephemeral=True
            )
            return

        except discord.HTTPException:
            logger.exception(
                "Erro HTTP ao registrar uso de farm."
            )

            await interaction.response.send_message(
                "❌ Ocorreu um erro ao registrar o uso "
                "da farm. Tente novamente.",
                ephemeral=True
            )
            return

        # -----------------------------------------------------
        # Envia informações de acesso por DM
        # -----------------------------------------------------
        dm_sent = True

        try:
            if self.farm == FARM_OPTIONS["cana"]:

                await self._send_access_dm(
                    farm_name="🎋 Farm de cana de açúcar",
                    warp=self.settings.farm_cana_warp,
                    password=self.settings.farm_cana_password
                )

            elif self.farm == FARM_OPTIONS["batata"]:

                if self.settings.farm_batata_indisponivel:

                    await self._send_potato_unavailable_dm()

                else:

                    await self._send_access_dm(
                        farm_name="🥔 Farm de batata",
                        warp=self.settings.farm_batata_warp,
                        password=self.settings.farm_batata_password
                    )

        except discord.Forbidden:
            dm_sent = False

            logger.info(
                "Não foi possível enviar DM para %s "
                "(DMs provavelmente desativadas).",
                self.member.id
            )

        except discord.HTTPException:
            dm_sent = False

            logger.exception(
                "Erro HTTP ao enviar DM para %s.",
                self.member.id
            )

        # -----------------------------------------------------
        # Resposta final
        # -----------------------------------------------------
        if dm_sent:

            await interaction.response.send_message(
                (
                    "✅ **Uso de farm registrado com sucesso!**\n\n"
                    f"**Farm:** {self.farm}\n"
                    f"**Horário:** {date_time}\n\n"
                    "🔐 As informações de acesso foram enviadas "
                    "no seu privado."
                ),
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                (
                    "✅ **Uso de farm registrado com sucesso!**\n\n"
                    f"**Farm:** {self.farm}\n"
                    f"**Horário:** {date_time}\n\n"
                    "⚠️ Não consegui enviar as informações "
                    "de acesso no seu privado. "
                    "Verifique se suas mensagens diretas "
                    "estão habilitadas."
                ),
                ephemeral=True
            )

    async def _send_access_dm(
        self,
        farm_name: str,
        warp: str,
        password: str
    ) -> None:

        message = (
            "🔐 **Dados de acesso da farm**\n\n"
            f"**Farm:** {farm_name}\n"
            f"**Warp:** `{warp}`\n"
            f"**Senha:** `{password}`\n\n"
            "⚠️ Não compartilhe essas informações."
        )

        await self.member.send(message)

    async def _send_potato_unavailable_dm(
        self
    ) -> None:

        message = (
            "Olá, a farm de batata está "
            "*indisponível no momento*.\n\n"
            "Atualmente, temos apenas a farm de cana de açúcar, "
            "verifique se ninguém está utilizando ela e utilize "
            "o comando `/registrar` e escolha: "
            "**Farm de cana de açúcar**.\n\n"
            "Atenciosamente, Vilaggergamerbr."
        )

        await self.member.send(message)


class FarmSelect(
    discord.ui.Select
):

    def __init__(
        self,
        settings: Settings,
        member: discord.Member
    ):
        self.settings = settings
        self.member = member

        options = [
            discord.SelectOption(
                label="Farm de cana de açúcar",
                value="cana",
                emoji="🎋",
                description="Registrar uso da farm de cana."
            ),
            discord.SelectOption(
                label="Farm de batata (EM CONSTRUÇÃO)",
                value="batata",
                emoji="🥔",
                description="Farm atualmente indisponível."
            ),
        ]

        super().__init__(
            placeholder="Selecione uma farm...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ) -> None:

        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Este menu não pertence a você.",
                ephemeral=True
            )
            return

        selected = self.values[0]

        farm = FARM_OPTIONS.get(selected)

        if farm is None:
            await interaction.response.send_message(
                "❌ Farm inválida.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            RegistrationModal(
                self.settings,
                self.member,
                farm
            )
        )


class FarmSelectionView(
    discord.ui.View
):

    def __init__(
        self,
        settings: Settings,
        member: discord.Member
    ):
        super().__init__(
            timeout=120
        )

        self.add_item(
            FarmSelect(
                settings,
                member
            )
        )