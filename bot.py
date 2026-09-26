from datetime import datetime, timezone
import hashlib
import os
import random
import re
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# ==============================================================================
# CONFIGURAÇÕES E IDs CONSTANTES
# ==============================================================================
CARGO_VERIFICADO_ID = 1546935292450312202
CARGO_NAO_VERIFICADO_ID = 1547044422913490964 # <-- NOVO CARGO ADICIONADO

CARGOS_TORNEIO = {
    "Alquimista": 1541613339942330499,
    "Pescador": 1541630361405231266,
    "Britadeira": 1541613312050200616,
    "Escavador": 1541626898663346237,
    "Builder": 1541612082569543784,
    "Fazendeiro": 1541613451909267497,
    "Slayer": 1541630332087050320,
    "Recruta": 1541613288096407642
}

# ==============================================================================
# BANCO DE DADOS LOCAL (SQLITE3)
# ==============================================================================
def setup_database():
    """Cria o banco de dados bot_database.db e as tabelas necessárias."""
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    
    # Tabela principal de sorteios usando AUTOINCREMENT
    c.execute('''CREATE TABLE IF NOT EXISTS sorteios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_cripto TEXT,
                    titulo TEXT,
                    descricao TEXT,
                    timestamp_termino INTEGER,
                    organizador_id INTEGER,
                    ganhadores INTEGER,
                    canal_id INTEGER,
                    mensagem_id INTEGER,
                    ativo INTEGER DEFAULT 1
                )''')
                
    # Tabela relacional de participantes x sorteio
    # A restrição UNIQUE impede que o mesmo user_id participe do mesmo sorteio duas vezes
    c.execute('''CREATE TABLE IF NOT EXISTS participantes (
                    id_cripto TEXT,
                    user_id INTEGER,
                    UNIQUE(id_cripto, user_id)
                )''')
                
    conn.commit()
    conn.close()

# Executa o setup de imediato
setup_database()

# ==============================================================================
# CLASSE PRINCIPAL DO BOT
# ==============================================================================
class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        
        # Adiciona as Views como persistentes para continuarem funcionando após reinício
        self.add_view(ViewTorneio())
        self.add_view(BotaoParticipar())
        
        # Inicia a checagem de sorteios no Background Loop
        check_giveaways.start()
        print("Comandos slash sincronizados com sucesso!")


client = Bot()


@client.event
async def on_ready():
    print(f"Bot conectado com sucesso como {client.user}")


# <-- NOVO EVENTO: Adiciona o cargo quando o membro entra no servidor
@client.event
async def on_member_join(member):
    cargo_nao_verificado = member.guild.get_role(CARGO_NAO_VERIFICADO_ID)
    
    if cargo_nao_verificado:
        try:
            await member.add_roles(cargo_nao_verificado)
            print(f"[INFO] Cargo 'Não Verificado' adicionado ao novato {member.name}.")
        except discord.Forbidden:
            print(f"[ERRO] Sem permissão para dar o cargo 'Não Verificado' para {member.name}.")
        except discord.HTTPException as e:
            print(f"[ERRO] Falha HTTP ao adicionar cargo 'Não Verificado': {e}")


# ==============================================================================
# SISTEMA DE VERIFICAÇÃO E CARGOS DO TORNEIO (Agora usando IDs em vez de Nomes)
# ==============================================================================
class MenuTorneio(discord.ui.Select):
    def __init__(self):
        opcoes = [
            discord.SelectOption(label="Alquimista", emoji="🧪", description="Torneio de Alquimista"),
            discord.SelectOption(label="Pescador", emoji="🐟", description="Torneio de Pesca"),
            discord.SelectOption(label="Britadeira", emoji="⛏️", description="Torneio Britadeira"),
            discord.SelectOption(label="Escavador", emoji="🧹", description="Torneio Escavador"),
            discord.SelectOption(label="Builder", emoji="✂️", description="Cargo de Builder"),
            discord.SelectOption(label="Fazendeiro", emoji="🌱", description="Torneio Farmer"),
            discord.SelectOption(label="Slayer", emoji="⚔️", description="Torneio Slayer"),
            discord.SelectOption(label="Recruta", emoji="❌", description="Sem cargos no torneio"),
        ]
        super().__init__(
            custom_id="menu_torneio_selecionar", # Custom ID fixo para persistência
            placeholder="Selecione seu(s) cargo(s) do torneio...",
            min_values=1,
            max_values=len(opcoes),
            options=opcoes
        )

    async def callback(self, interaction: discord.Interaction):
        # Evita timeout do Discord
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        member = interaction.user
        
        cargos_encontrados = []
        cargos_falhos = []

        for cargo_nome in self.values:
            cargo_id = CARGOS_TORNEIO.get(cargo_nome)
            cargo = guild.get_role(cargo_id) if cargo_id else None
            
            if cargo:
                cargos_encontrados.append(cargo)
            else:
                cargos_falhos.append(cargo_nome)

        if cargos_encontrados:
            try:
                await member.add_roles(*cargos_encontrados)
            except discord.Forbidden:
                print(f"[ERRO] Bot não possui permissão para dar cargos a {member.name}.")
            except discord.HTTPException as e:
                print(f"[ERRO] Falha HTTP ao adicionar cargos: {e}")

        nomes_adicionados = ", ".join([c.name for c in cargos_encontrados])
        mensagem = f"✅ Sucesso! Você recebeu os seguintes cargos: **{nomes_adicionados}**"
     
        if cargos_falhos:
            mensagem += f"\n⚠️ Erro: Não encontrei os cargos {', '.join(cargos_falhos)} no servidor. Avise um Líder!"

        # Mudado de response.send_message para followup.send por causa do defer()
        await interaction.followup.send(mensagem, ephemeral=True)


class ViewTorneio(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MenuTorneio())


class FormularioVerificacao(discord.ui.Modal, title="Painel de Verificação"):
    nome_minecraft = discord.ui.TextInput(
        label="Digite o seu nome no Minecraft:",
        placeholder="...",
        max_length=32,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        nome_escolhido = self.nome_minecraft.value

        # Busca pelos IDs numéricos
        cargo_verificado = guild.get_role(CARGO_VERIFICADO_ID)
        cargo_nao_verificado = guild.get_role(CARGO_NAO_VERIFICADO_ID) # <-- NOVO

        if not cargo_verificado:
            await interaction.response.send_message(
                "Cargo 'Verificado' não encontrado no servidor. O ID no código pode estar incorreto.",
                ephemeral=True,
            )
            return

        # Substituindo o except Exception genérico por exceções específicas e logging
        try:
            await member.edit(nick=nome_escolhido)
        except discord.Forbidden:
            print(f"[AVISO] O bot não tem permissão acima do cargo de {member.name} para trocar o nick.")
        except discord.HTTPException as e:
            print(f"[ERRO] Erro na API do Discord ao tentar mudar nick de {member.name}: {e}")

        try:
            # <-- MODIFICADO: Adiciona o verificado E remove o não verificado
            await member.add_roles(cargo_verificado)
            if cargo_nao_verificado and cargo_nao_verificado in member.roles:
                await member.remove_roles(cargo_nao_verificado)
        except discord.Forbidden:
            print(f"[AVISO] Sem permissão para gerenciar os cargos de verificação de {member.name}.")
        except discord.HTTPException as e:
            print(f"[ERRO] HTTP Exception ao alterar cargos de {member.name}: {e}")

        await interaction.response.send_message(
            f"Tudo pronto, {member.mention}! Seu nick foi alterado para **{nome_escolhido}**.\n\n"
            "👇 **Agora, selecione qual(is) torneios/cargos você quer participar abaixo:**",
            view=ViewTorneio(),
            ephemeral=True,
        )


@client.tree.command(
    name="verificar",
    description="Inicia sua verificação informando seu nick do Minecraft.",
)
async def verificar(interaction: discord.Interaction):
    guild = interaction.guild
    member = interaction.user
    cargo = guild.get_role(CARGO_VERIFICADO_ID)

    if cargo and cargo in member.roles:
        await interaction.response.send_message(
            "Você já está verificado no servidor.", ephemeral=True
        )
        return

    await interaction.response.send_modal(FormularioVerificacao())


# ==============================================================================
# SISTEMA DE SORTEIOS PERSISTENTES (COM BANCO DE DADOS E TASKS.LOOP)
# ==============================================================================
def converter_tempo(tempo_str: str) -> int:
    match = re.match(r"^(\d+)([a-zA-Z])$", tempo_str.strip())
    if not match: return None
    quantidade = int(match.group(1))
    unidade = match.group(2)
    multiplicadores = {"s": 1, "m": 60, "h": 3600, "d": 86400, "M": 2592000, "a": 31536000}
    if unidade not in multiplicadores: return None
    return quantidade * multiplicadores[unidade]

def gerar_id_criptografado(numero_sorteio: int) -> str:
    texto_base = f"{numero_sorteio}-Embrapa"
    hash_obj = hashlib.sha256(texto_base.encode("utf-8"))
    return hash_obj.hexdigest()[:10]


class BotaoParticipar(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Participar", style=discord.ButtonStyle.primary, emoji="🎉", custom_id="botao_sorteio_participar"
    )
    async def participar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Evita o erro 404 de timeout do Discord
        await interaction.response.defer(ephemeral=True)
        
        msg_id = interaction.message.id
        user_id = interaction.user.id
        
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        
        c.execute("SELECT id_cripto, organizador_id FROM sorteios WHERE mensagem_id = ? AND ativo = 1", (msg_id,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            # Como usamos defer(), agora usamos followup para enviar mensagens ocultas
            await interaction.followup.send("❌ Este sorteio já acabou ou foi deletado!", ephemeral=True)
            return
            
        id_cripto, organizador_id = row
        
        try:
            c.execute("INSERT INTO participantes (id_cripto, user_id) VALUES (?, ?)", (id_cripto, user_id))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            await interaction.followup.send("Você já está participando deste sorteio!", ephemeral=True)
            return
            
        c.execute("SELECT COUNT(*) FROM participantes WHERE id_cripto = ?", (id_cripto,))
        total_participantes = c.fetchone()[0]
        conn.close()
        
        await interaction.followup.send("✅ Sua participação foi registrada com sucesso!", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            0,
            name="",
            value=(f"Organizado por: <@{organizador_id}>\nNúmero de participantes: {total_participantes}\nTerminará em breve..."),
            inline=False,
        )
        
        try:
            await interaction.message.edit(embed=embed)
        except discord.HTTPException as e:
            print(f"[ERRO] Erro visual ao atualizar contagem de participantes no Embed: {e}")


async def finalizar_sorteio_logica(id_cripto: str, forcar_vencedores: bool = True):
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    
    # 1. Obter dados originais da tabela de sorteios
    c.execute("SELECT titulo, descricao, organizador_id, ganhadores, canal_id, mensagem_id FROM sorteios WHERE id_cripto = ? AND ativo = 1", (id_cripto,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return
        
    titulo, desc, organizador_id, ganhadores, canal_id, mensagem_id = row
    
    # 2. Obter lista de usuários que participaram
    c.execute("SELECT user_id FROM participantes WHERE id_cripto = ?", (id_cripto,))
    lista_participantes = [r[0] for r in c.fetchall()]
    
    # 3. Marcar como finalizado no DB
    c.execute("UPDATE sorteios SET ativo = 0 WHERE id_cripto = ?", (id_cripto,))
    conn.commit()
    conn.close()

    # 4. Encontrar os canais e mensagens para edição
    canal = client.get_channel(canal_id)
    if not canal:
        print(f"[ERRO] Não foi possível encontrar o canal (ID:{canal_id}) para finalizar o sorteio {id_cripto}.")
        return

    try:
        mensagem = await canal.fetch_message(mensagem_id)
    except discord.NotFound:
        print(f"[AVISO] A mensagem original do sorteio {id_cripto} foi excluída manualmente. Sorteio apenas logado como fechado.")
        mensagem = None
    except discord.HTTPException as e:
        print(f"[ERRO] API error ao tentar buscar mensagem do sorteio {id_cripto}: {e}")
        mensagem = None

    data_fim = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    min_participantes = 3 if ganhadores == 1 else ganhadores * 2
    embed_final = discord.Embed(title=titulo, description=desc, color=discord.Color.from_rgb(52, 235, 119))
    
    # View "morta" (desabilitada) que será anexada para os botões não sumirem mas pararem de funcionar
    view_final = BotaoParticipar()
    for child in view_final.children:
        child.disabled = True

    if forcar_vencedores and len(lista_participantes) >= min_participantes:
        qtd_vencedores = min(ganhadores, len(lista_participantes))
        vencedores_ids = random.sample(lista_participantes, qtd_vencedores)
        mencoes_vencedores = ", ".join([f"<@{uid}>" for uid in vencedores_ids])
        
        embed_final.add_field(name="", value=(f"Vencedores: {mencoes_vencedores}\nOrganizado por: <@{organizador_id}>\nNúmero de participantes: {len(lista_participantes)}"), inline=False)
        embed_final.set_footer(text=f"Terminado em • {data_fim} | ID: {id_cripto}")
        
        if mensagem:
            try:
                await mensagem.edit(embed=embed_final, view=view_final)
            except discord.HTTPException as e:
                print(f"[ERRO] Erro ao editar mensagem final de vitória: {e}")
        
        try:
            await canal.send(f"Sorteio finalizado. Parabéns aos vencedores! 🎉 ({mencoes_vencedores})")
        except discord.Forbidden:
            print(f"[ERRO] O Bot não tem permissão de mandar mensagens no canal do Sorteio (ID {canal_id}).")

    else:
        embed_final.color = discord.Color.from_rgb(200, 200, 200)
        embed_final.add_field(name="", value=(f"Vencedores: *Cancelado por falta de participantes*\nOrganizado por: <@{organizador_id}>\nNúmero de participantes: {len(lista_participantes)}"), inline=False)
        embed_final.set_footer(text=f"Terminado em • {data_fim} | ID: {id_cripto}")
        
        if mensagem:
            try:
                await mensagem.edit(embed=embed_final, view=view_final)
            except discord.HTTPException as e:
                print(f"[ERRO] Erro ao editar mensagem de cancelamento: {e}")
                
        try:
            await canal.send(f"Sorteio finalizado, mas não atingiu o número mínimo de participantes (mínimo necessário: {min_participantes}).")
        except discord.Forbidden:
            print(f"[ERRO] O Bot não tem permissão de mandar mensagens de cancelamento no canal do Sorteio (ID {canal_id}).")


# ------------------------------------------------------------------------------
# TIMER SUBSTITUTO: Loop que roda a cada 10 segundos verificando quem venceu
# ------------------------------------------------------------------------------
@tasks.loop(seconds=10)
async def check_giveaways():
    agora_timestamp = int(datetime.now(timezone.utc).timestamp())
    
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    # Puxa o ID Cripto de sorteios ainda ativos (1) onde o tempo limite já passou
    c.execute("SELECT id_cripto FROM sorteios WHERE ativo = 1 AND timestamp_termino <= ?", (agora_timestamp,))
    vencidos = c.fetchall()
    conn.close()

    for (id_cripto,) in vencidos:
        # Repassa para nossa lógica finalizar perfeitamente o embed
        await finalizar_sorteio_logica(id_cripto, forcar_vencedores=True)


@app_commands.default_permissions(administrator=True)
class SorteioGroup(app_commands.Group):
    pass

sorteio_group = SorteioGroup(name="sorteio", description="Gerencia os sorteios do servidor")


@sorteio_group.command(name="criar", description="Cria um novo sorteio interativo e persiste na base de dados.")
@app_commands.describe(title="Título", desc="Descrição", time="Tempo (ex: 30s, 10m, 2h)", ganhadores="Vencedores")
async def criar(interaction: discord.Interaction, title: str, desc: str, time: str, ganhadores: int):
    segundos = converter_tempo(time)
    if not segundos or segundos <= 0:
        await interaction.response.send_message("❌ Tempo inválido! Ex: `2d`", ephemeral=True)
        return
    if ganhadores < 1:
        await interaction.response.send_message("❌ O número de ganhadores deve ser pelo menos 1.", ephemeral=True)
        return

    timestamp_termino = int(datetime.now(timezone.utc).timestamp()) + segundos
    
    # Insere primeiramente para obtermos o Auto-Increment numérico via banco de dados
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO sorteios (titulo, descricao, timestamp_termino, organizador_id, ganhadores, canal_id, mensagem_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, desc, timestamp_termino, interaction.user.id, ganhadores, interaction.channel.id, 0)
    )
    
    # O identificador do sorteio nunca reseta do zero usando este lastrowid
    sorteio_db_id = c.lastrowid
    id_cripto = gerar_id_criptografado(sorteio_db_id)
    
    data_inicio = datetime.now().strftime("%d/%m/%Y %H:%M")
    embed = discord.Embed(title=title, description=desc, color=discord.Color.from_rgb(235, 64, 52))
    embed.add_field(name="", value=(f"Organizado por: {interaction.user.mention}\nNúmero de participantes: 0\nTerminará em breve..."), inline=False)
    embed.set_footer(text=f"Começado em • {data_inicio} | ID: {id_cripto}")

    view = BotaoParticipar()
    await interaction.response.send_message(f"🎉 Sorteio criado com sucesso! ID: `{id_cripto}`", ephemeral=True)
    mensagem_sorteio = await interaction.channel.send(embed=embed, view=view)

    # Agora faz o UPDATE pra inserir o ID encriptografado e o ID da mensagem verdadeira
    c.execute("UPDATE sorteios SET id_cripto = ?, mensagem_id = ? WHERE id = ?", (id_cripto, mensagem_sorteio.id, sorteio_db_id))
    conn.commit()
    conn.close()


@sorteio_group.command(name="excluir", description="Exclui um sorteio em andamento apagando-o do banco de dados.")
@app_commands.describe(id="ID do sorteio")
async def excluir(interaction: discord.Interaction, id: str):
    id_limpo = id.strip()
    
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute("SELECT canal_id, mensagem_id FROM sorteios WHERE id_cripto = ? AND ativo = 1", (id_limpo,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        await interaction.response.send_message("❌ Nenhum sorteio ativo encontrado com esse ID.", ephemeral=True)
        return
        
    canal_id, mensagem_id = row
    
    # Define como Inativo no Banco
    c.execute("UPDATE sorteios SET ativo = 0 WHERE id_cripto = ?", (id_limpo,))
    conn.commit()
    conn.close()
    
    canal = client.get_channel(canal_id)
    if canal:
        try:
            mensagem = await canal.fetch_message(mensagem_id)
            await mensagem.delete()
        except discord.NotFound:
            print(f"[AVISO] Tentativa de excluir sorteio {id_limpo}, mas a mensagem original já foi apagada no Discord.")
        except discord.Forbidden:
            print(f"[ERRO] O Bot não possui as permissões necessárias de Gerenciar Mensagens para apagar o Sorteio {id_limpo}.")
        except discord.HTTPException as e:
            print(f"[ERRO] Erro na API do Discord ao excluir sorteio {id_limpo}: {e}")
            
    await interaction.response.send_message(f"🗑️ O sorteio `{id_limpo}` foi cancelado e excluído com sucesso.", ephemeral=True)


@sorteio_group.command(name="finalizar", description="Finaliza antecipadamente um sorteio via Banco de Dados.")
@app_commands.describe(id="ID do sorteio")
async def finalizar(interaction: discord.Interaction, id: str):
    id_limpo = id.strip()
    
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute("SELECT ativo FROM sorteios WHERE id_cripto = ? AND ativo = 1", (id_limpo,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        await interaction.response.send_message("❌ Nenhum sorteio ativo encontrado com esse ID.", ephemeral=True)
        return
        
    await interaction.response.send_message(f"🏁 Finalizando o sorteio `{id_limpo}`...", ephemeral=True)
    await finalizar_sorteio_logica(id_limpo, forcar_vencedores=True)

client.tree.add_command(sorteio_group)


# ==============================================================================
# EXECUÇÃO DO BOT
# ==============================================================================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)