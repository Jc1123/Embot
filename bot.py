import discord
from discord import app_commands
from discord.ext import commands
import os
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


client = Bot ()


@client.event
async def on_ready():
  print(f"Bot conectado com sucesso como {client.user}")

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

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

client.run(TOKEN)