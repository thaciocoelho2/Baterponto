import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import uuid
from datetime import datetime
import pytz
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÕES ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BR_TZ = pytz.timezone('America/Sao_Paulo')

# ⚠️ AJUSTE SEU ID E LINKS AQUI
ID_DONO = 123456789012345678  
LINK_PAGAMENTO = "https://seu-link-aqui.com" 
SENHA_LIBERACAO = "PONTO_2024_PRO" 

# --- 2. BANCO DE DADOS ---
def carregar_dados():
    try:
        with open('database.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: 
        return {"servidores": {}, "chaves_ativas": []}

def salvar_dados(dados):
    with open('database.json', 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# --- 3. INTERFACES (VIEWS) ---
# Definimos as classes DEPOIS dos imports para evitar o erro "NameError"

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fechar Ticket", style=discord.ButtonStyle.secondary, custom_id="close_tkt")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Este ticket será excluído em 5 segundos...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Abrir Ticket / Resgatar Chave", style=discord.ButtonStyle.primary, custom_id="open_tkt")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        nome_canal = f"ticket-{interaction.user.name.lower()}"
        
        existente = discord.utils.get(guild.channels, name=nome_canal)
        if existente:
            return await interaction.response.send_message(f"⚠️ Você já possui um ticket aberto: {existente.mention}", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        canal = await guild.create_text_channel(nome_canal, overwrites=overwrites)
        
        embed = discord.Embed(
            title="🎫 Suporte & Auto-Resgate",
            description=(
                f"Olá {interaction.user.mention}!\n\n"
                "**🤖 COMPROU E QUER A CHAVE AGORA?**\n"
                "Se você já tem a senha do PDF de compra, use o comando:\n"
                "`/resgatar senha: SUA_SENHA_AQUI`"
            ),
            color=discord.Color.blue()
        )
        await canal.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✅ Ticket criado em {canal.mention}", ephemeral=True)

class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def registrar(self, interaction: discord.Interaction, tipo: str):
        sid = str(interaction.guild.id)
        dados = carregar_dados()

        if sid not in dados["servidores"]:
            view_venda = discord.ui.View()
            view_venda.add_item(discord.ui.Button(label="Assinar Agora", url=LINK_PAGAMENTO))
            return await interaction.response.send_message("🔒 Servidor sem assinatura ativa.", view=view_venda, ephemeral=True)

        agora = datetime.now(BR_TZ).strftime("%H:%M:%S")
        await interaction.response.send_message(f"✅ {tipo} registrada às `{agora}`", ephemeral=True)

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="btn_ent")
    async def ent(self, i, b): await self.registrar(i, "Entrada")

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="btn_sai")
    async def sai(self, i, b): await self.registrar(i, "Saída")

# --- 4. CLASSE DO BOT ---

class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(TicketOpenView())
        self.add_view(TicketControlView())
        self.add_view(PontoView())
        await self.tree.sync()
        print(f"✅ Bot online como: {self.user}")

bot = PontoBot()

# --- 5. COMANDOS ---

@bot.tree.command(name="ponto", description="Abre o painel de ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Central de Ponto", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView())

@bot.tree.command(name="setup_suporte", description="Configura os tickets")
async def setup_suporte(interaction: discord.Interaction):
    if interaction.user.id != ID_DONO: return
    embed = discord.Embed(title="🆘 Suporte", description="Clique abaixo para suporte ou resgate.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=TicketOpenView())
    await interaction.response.send_message("✅ Painel configurado!", ephemeral=True)

@bot.tree.command(name="resgatar", description="Gera sua chave automaticamente")
async def resgatar(interaction: discord.Interaction, senha: str):
    if senha == SENHA_LIBERACAO:
        nova_chave = f"PROMO-{str(uuid.uuid4())[:8].upper()}"
        dados = carregar_dados()
        dados["chaves_ativas"].append(nova_chave)
        salvar_dados(dados)
        await interaction.response.send_message(f"🔑 Chave: `{nova_chave}`\nUse `/ativar` no seu servidor.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Senha incorreta.", ephemeral=True)

@bot.tree.command(name="ativar", description="Ativa a licença")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        dados["servidores"][str(interaction.guild.id)] = {"usuarios": {}}
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 Licença Pro ativada!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Chave inválida.", ephemeral=True)

bot.run(TOKEN)