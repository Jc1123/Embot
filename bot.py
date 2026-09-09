from datetime import datetime, timezone
import os
import random
import re
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class Bot(commands.Bot):

  def __init__(self):
    super().__init__(command_prefix="!", intents=intents)

  async def setup_hook(self):
    await self.tree.sync()
    print("Comandos slash sincronizados com sucesso!")


client = Bot()


@client.event
async def on_ready():
  print(f"Bot conectado com sucesso como {client.user}")


# --- SISTEMA DE VERIFICAÇÃO (Já existente) ---
class FormularioVerificacao(discord.ui.Modal, title="Painel de Verificação"):
  nome_minecraft = discord.ui.TextInput(
      label="Digite o seu nome do Minecraft:",
      placeholder="...",
      max_length=32,
      required=True,
  )

  async def on_submit(self, interaction: discord.Interaction):
    guild = interaction.guild
    member = interaction.user
    nome_escolhido = self.nome_minecraft.value

    cargo = discord.utils.get(guild.roles, name="Verificado")

    if not cargo:
      await interaction.response.send_message(
          "Cargo 'Verificado' não encontrado no servidor. Contate um líder.",
          ephemeral=True,
      )
      return

    try:
      await member.edit(nick=nome_escolhido)
    except Exception:
      pass

    await member.add_roles(cargo)

    await interaction.response.send_message(
        f"Tudo pronto, {member.mention}! Você está verificado com o nick"
        f" **{nome_escolhido}**.",
        ephemeral=True,
    )


@client.tree.command(
    name="verificar",
    description="Inicia sua verificação informando seu nick do Minecraft.",
)
async def verificar(interaction: discord.Interaction):
  guild = interaction.guild
  member = interaction.user

  cargo = discord.utils.get(guild.roles, name="Verificado")

  if not cargo:
    await interaction.response.send_message(
        "Cargo 'Verificado' não encontrado no servidor. Contate um líder.",
        ephemeral=True,
    )
    return

  if cargo in member.roles:
    await interaction.response.send_message(
        "Você já está verificado.", ephemeral=True
    )
    return

  await interaction.response.send_modal(FormularioVerificacao())


# --- SISTEMA DE SORTEIOS ---

# Função para converter o formato de tempo (ex: 2d, 30m, 1h) em segundos
def converter_tempo(tempo_str: str) -> int:
  match = re.match(r"^(\d+)([a-zA-Z])$", tempo_str.strip())
  if not match:
    return None

  quantidade = int(match.group(1))
  unidade = match.group(2)

  multiplicadores = {
      "s": 1,  # Segundos
      "m": 60,  # Minutos
      "h": 3600,  # Horas
      "d": 86400,  # Dias
      "M": 2592000,  # Meses (aprox. 30 dias)
      "a": 31536000,  # Anos (aprox. 365 dias)
  }

  if unidade not in multiplicadores:
    return None

  return quantidade * multiplicadores[unidade]


# Botão de Participar do Sorteio
class BotaoParticipar(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)  # Mantém o botão ativo permanentemente
    self.participantes = set()  # Armazena os IDs para evitar duplicadas

  @discord.ui.button(
      label="Participar",
      style=discord.ButtonStyle.primary,
      emoji="🎉",
      custom_id="botao_sorteio_participar",
  )
  async def participar(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if interaction.user.id in self.participantes:
      await interaction.response.send_message(
          "Você já está participando deste sorteio!", ephemeral=True
      )
    else:
      self.participantes.add(interaction.user.id)
      await interaction.response.send_message(
          "✅ Sua participação foi registrada com sucesso!", ephemeral=True
      )


# Grupo de comandos /sorteio
class SorteioGroup(app_commands.Group):
  pass


sorteio_group = SorteioGroup(
    name="sorteio", description="Gerencia os sorteios do servidor"
)


@sorteio_group.command(
    name="criar", description="Cria um novo sorteio interativo no canal."
)
@app_commands.describe(
    title="Título do sorteio",
    desc="Descrição detalhada do prêmio",
    time="Tempo de duração (ex: 30s, 10m, 2h, 2d)",
    ganhadores="Número de vencedores",
)
async def criar(
    interaction: discord.Interaction,
    title: str,
    desc: str,
    time: str,
    ganhadores: int,
):
  # Valida o tempo informado
  segundos = converter_tempo(time)
  if not segundos or segundos <= 0:
    await interaction.response.send_message(
        "❌ Formato de tempo inválido! Use números seguidos de: **s** (segundos),"
        " **m** (minutos), **h** (horas), **d** (dias), **M** (meses) ou **a**"
        " (anos). Ex: `2d`",
        ephemeral=True,
    )
    return

  if ganhadores < 1:
    await interaction.response.send_message(
        "❌ O número de ganhadores deve ser pelo menos 1.", ephemeral=True
    )
    return

  data_inicio = datetime.now().strftime("%d/%m/%Y %H:%M")

  # Cria o Embed inicial do Sorteio
  embed = discord.Embed(
      title=title, description=desc, color=discord.Color.from_rgb(235, 64, 52)
  )
  embed.add_field(
      name="",
      value=(
          f"Organizado por: {interaction.user.mention}\nTerminará em breve..."
      ),
      inline=False,
  )
  embed.set_footer(text=f"Começado em • {data_inicio}")

  view = BotaoParticipar()

  # Responde o comando criando a mensagem do sorteio no canal
  await interaction.response.send_message(
      "🎉 Sorteio iniciado com sucesso!", ephemeral=True
  )
  mensagem_sorteio = await interaction.channel.send(embed=embed, view=view)

  # Aguarda o tempo estipulado rodando em segundo plano
  await asyncio.sleep(segundos)

  # --- FASE DE ENCERRAMENTO DO SORTEIO ---
  data_fim = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
  lista_participantes = list(view.participantes)

  embed_final = discord.Embed(
      title=title, description=desc, color=discord.Color.from_rgb(52, 235, 119)
  )

  if len(lista_participantes) > 0:
    # Sorteia os vencedores de forma totalmente aleatória
    qtd_vencedores = min(ganhadores, len(lista_participantes))
    vencedores_ids = random.sample(lista_participantes, qtd_vencedores)
    mencoes_vencedores = ", ".join([f"<@{uid}>" for uid in vencedores_ids])

    embed_final.add_field(
        name="",
        value=(
            f"Vencedores: {mencoes_vencedores}\nOrganizado por:"
            f" {interaction.user.mention}"
        ),
        inline=False,
    )
    embed_final.set_footer(text=f"Terminado em • {data_fim}")

    # Desativa o botão para ninguém mais clicar
    for child in view.children:
      child.disabled = True

    await mensagem_sorteio.edit(embed=embed_final, view=view)

    # Mensagem de encerramento no chat
    await interaction.channel.send(
        f"Sorteio finalizado. Parabéns aos vencedores! 🎉 ({mencoes_vencedores})"
    )

  else:
    # Caso ninguém tenha participado
    embed_final.add_field(
        name="",
        value=(
            f"Vencedores: *Nenhum participante*\nOrganizado por:"
            f" {interaction.user.mention}"
        ),
        inline=False,
    )
    embed_final.set_footer(text=f"Terminado em • {data_fim}")

    for child in view.children:
      child.disabled = True

    await mensagem_sorteio.edit(embed=embed_final, view=view)
    await interaction.channel.send(
        "Sorteio finalizado, mas infelizmente não houve participantes."
    )


# Registra o grupo de comandos no bot principal
client.tree.add_command(sorteio_group)

# --- EXECUÇÃO DO BOT ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)