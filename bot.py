from datetime import datetime, timezone
import hashlib
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


# --- SISTEMA DE VERIFICAÇÃO ---
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

sorteios_ativos = {}


def converter_tempo(tempo_str: str) -> int:
  match = re.match(r"^(\d+)([a-zA-Z])$", tempo_str.strip())
  if not match:
    return None

  quantidade = int(match.group(1))
  unidade = match.group(2)

  multiplicadores = {
      "s": 1,
      "m": 60,
      "h": 3600,
      "d": 86400,
      "M": 2592000,
      "a": 31536000,
  }

  if unidade not in multiplicadores:
    return None

  return quantidade * multiplicadores[unidade]


def gerar_id_criptografado(numero_sorteio: int) -> str:
  texto_base = f"{numero_sorteio}-Embrapa"
  hash_obj = hashlib.sha256(texto_base.encode("utf-8"))
  return hash_obj.hexdigest()[:10]


# Botão de Participar com contagem dinâmica
class BotaoParticipar(discord.ui.View):

  def __init__(self, organizador_mention: str):
    super().__init__(timeout=None)
    self.participantes = set()
    self.organizador_mention = organizador_mention

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
      
      # Responde primeiro para evitar erro de timeout na interação
      await interaction.response.send_message(
          "✅ Sua participação foi registrada com sucesso!", ephemeral=True
      )
      
      # Em seguida, atualiza o Embed com o novo número de participantes
      embed = interaction.message.embeds[0]
      embed.set_field_at(
          0,
          name="",
          value=(
              f"Organizado por: {self.organizador_mention}\n"
              f"Número de participantes: {len(self.participantes)}\n"
              "Terminará em breve..."
          ),
          inline=False,
      )
      await interaction.message.edit(embed=embed)


contador_sorteios = 0


async def finalizar_sorteio_logica(
    id_cripto: str, forcar_vencedores: bool = True
):
  if id_cripto not in sorteios_ativos:
    return

  dados = sorteios_ativos[id_cripto]
  task = dados["task"]
  mensagem = dados["mensagem"]
  view = dados["view"]
  title = dados["title"]
  desc = dados["desc"]
  organizador = dados["organizador"]
  ganhadores = dados["ganhadores"]
  canal = dados["canal"]

  if not task.done():
    task.cancel()

  data_fim = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
  lista_participantes = list(view.participantes)
  
  # Calcula o mínimo de participantes exigido pela regra
  min_participantes = 3 if ganhadores == 1 else ganhadores * 2

  embed_final = discord.Embed(
      title=title, description=desc, color=discord.Color.from_rgb(52, 235, 119)
  )

  # Checa se bateu a meta de participantes
  if forcar_vencedores and len(lista_participantes) >= min_participantes:
    qtd_vencedores = min(ganhadores, len(lista_participantes))
    vencedores_ids = random.sample(lista_participantes, qtd_vencedores)
    mencoes_vencedores = ", ".join([f"<@{uid}>" for uid in vencedores_ids])

    embed_final.add_field(
        name="",
        value=(
            f"Vencedores: {mencoes_vencedores}\n"
            f"Organizado por: {organizador.mention}\n"
            f"Número de participantes: {len(lista_participantes)}"
        ),
        inline=False,
    )
    embed_final.set_footer(text=f"Terminado em • {data_fim} | ID: {id_cripto}")

    for child in view.children:
      child.disabled = True

    try:
      await mensagem.edit(embed=embed_final, view=view)
    except Exception:
      pass

    await canal.send(
        f"Sorteio finalizado. Parabéns aos vencedores! 🎉 ({mencoes_vencedores})"
    )
    
  else:
    # Caso não atinja a proporção de 2:1 ou os 3 mínimos
    embed_final.color = discord.Color.from_rgb(200, 200, 200) # Cor cinza
    embed_final.add_field(
        name="",
        value=(
            f"Vencedores: *Cancelado por falta de participantes*\n"
            f"Organizado por: {organizador.mention}\n"
            f"Número de participantes: {len(lista_participantes)}"
        ),
        inline=False,
    )
    embed_final.set_footer(text=f"Terminado em • {data_fim} | ID: {id_cripto}")

    for child in view.children:
      child.disabled = True

    try:
      await mensagem.edit(embed=embed_final, view=view)
    except Exception:
      pass

    await canal.send(
        f"Sorteio finalizado, mas não atingiu o número mínimo de participantes "
        f"(mínimo necessário: {min_participantes})."
    )

  del sorteios_ativos[id_cripto]


@app_commands.default_permissions(administrator=True)
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
  global contador_sorteios
  contador_sorteios += 1

  id_cripto = gerar_id_criptografado(contador_sorteios)

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

  embed = discord.Embed(
      title=title, description=desc, color=discord.Color.from_rgb(235, 64, 52)
  )
  embed.add_field(
      name="",
      value=(
          f"Organizado por: {interaction.user.mention}\n"
          f"Número de participantes: 0\n"
          "Terminará em breve..."
      ),
      inline=False,
  )
  embed.set_footer(text=f"Começado em • {data_inicio} | ID: {id_cripto}")

  view = BotaoParticipar(interaction.user.mention)

  await interaction.response.send_message(
      f"🎉 Sorteio criado com sucesso! ID: `{id_cripto}`", ephemeral=True
  )
  mensagem_sorteio = await interaction.channel.send(embed=embed, view=view)

  async def temporizador_sorteio():
    try:
      await asyncio.sleep(segundos)
      await finalizar_sorteio_logica(id_cripto, forcar_vencedores=True)
    except asyncio.CancelledError:
      pass

  task = asyncio.create_task(temporizador_sorteio())

  sorteios_ativos[id_cripto] = {
      "task": task,
      "mensagem": mensagem_sorteio,
      "view": view,
      "title": title,
      "desc": desc,
      "organizador": interaction.user,
      "ganhadores": ganhadores,
      "canal": interaction.channel,
  }


@sorteio_group.command(
    name="excluir",
    description="Exclui um sorteio em andamento sem sortear ganhadores.",
)
@app_commands.describe(id="ID do sorteio que deseja excluir")
async def excluir(interaction: discord.Interaction, id: str):
  id_limpo = id.strip()

  if id_limpo not in sorteios_ativos:
    await interaction.response.send_message(
        "❌ Nenhum sorteio ativo foi encontrado com esse ID.", ephemeral=True
    )
    return

  dados = sorteios_ativos[id_limpo]
  dados["task"].cancel()

  try:
    await dados["mensagem"].delete()
  except Exception:
    pass

  del sorteios_ativos[id_limpo]

  await interaction.response.send_message(
      f"🗑️ O sorteio com ID `{id_limpo}` foi cancelado e excluído com"
      " sucesso.",
      ephemeral=True,
  )


@sorteio_group.command(
    name="finalizar",
    description=(
        "Finaliza antecipadamente um sorteio em andamento e escolhe os"
        " ganhadores."
    ),
)
@app_commands.describe(id="ID do sorteio que deseja finalizar")
async def finalizar(interaction: discord.Interaction, id: str):
  id_limpo = id.strip()

  if id_limpo not in sorteios_ativos:
    await interaction.response.send_message(
        "❌ Nenhum sorteio ativo foi encontrado com esse ID.", ephemeral=True
    )
    return

  await interaction.response.send_message(
      f"🏁 Finalizando o sorteio `{id_limpo}` antecipadamente...", ephemeral=True
  )
  await finalizar_sorteio_logica(id_limpo, forcar_vencedores=True)


client.tree.add_command(sorteio_group)

# --- EXECUÇÃO DO BOT ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)