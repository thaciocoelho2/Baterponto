import discord
from discord.ext import commands
from discord import app_commands
import json, os, asyncio, uuid, pytz
from datetime import datetime
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÕES ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BR_TZ = pytz.timezone('America/Sao_Paulo')

# ⚠️ AJUSTE SEUS DADOS AQUI
ID_DONO = 123456789012345678  # Seu ID numérico
LINK_PAGAMENTO = "https://seu-link-aqui.com" 
SENHA_LIBERACAO = "PONTO_2024_PRO" 

# --- 2. BANCO DE DADOS ---
def carregar_dados():
    try:
        if not os.path.exists('database.json'):
            return {"servidores": {}, "chaves_ativas": []}
        with open('database.json', 'r', encoding='utf-8') as f:
            content = f.read()
            return json.loads(content) if content else {"servidores": {}, "chaves_ativas": []}
    except Exception as e:
        print(f"Erro ao carregar banco: {e}")
        return {"servidores": {}, "chaves_ativas": []}

def salvar_dados(dados):
    try:
        with open('database.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar banco: {e}")

# --- 3. INTERFACES (VIEWS) ---

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="🔒 Fechar Ticket", style=discord.ButtonStyle.secondary, custom_id="close_tkt")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Encerrando atendimento em 3 segundos...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="📩 Suporte / Resgatar Chave", style=discord.ButtonStyle.primary, custom_id="open_tkt")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        canal = await guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites)
        embed = discord.Embed(title="🎫 Suporte Ponto Bot", description="Se você comprou, use `/resgatar` com a senha do PDF.", color=discord.Color.blue())
        await canal.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"Ticket criado: {canal.mention}", ephemeral=True)

class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    async def registrar(self, interaction: discord.Interaction, tipo: str):
        sid = str(interaction.guild.id)
        dados = carregar_dados()
        if sid not in dados["servidores"]:
            v_venda = discord.ui.View()
            v_venda.add_item(discord.ui.Button(label="Assinar Agora", url=LINK_PAGAMENTO))
            return await interaction.response.send_message("🔒 Servidor sem assinatura ativa.", view=v_venda, ephemeral=True)
        agora = datetime.now(BR_TZ).strftime("%H:%M:%S")
        await interaction.response.send_message(f"✅ {tipo} registrada: `{agora}`", ephemeral=True)
    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="btn_ent")
    async def ent(self, i, b): await self.registrar(i, "Entrada")
    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="btn_sai")
    async def sai(self, i, b): await self.registrar(i, "Saída")

# --- 4. CLASSE DO BOT ---
class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(TicketOpenView())
        self.add_view(TicketControlView())
        self.add_view(PontoView())
        await self.tree.sync()
        print(f"✅ Bot logado como: {self.user}")

bot = PontoBot()

# --- 5. COMANDOS ---

@bot.tree.command(name="ponto", description="Abre o painel de ponto")
async def ponto(interaction: discord.Interaction):
    await interaction.response.send_message("🗓️ Central de Ponto", view=PontoView())

@bot.tree.command(name="setup_suporte", description="Configura os tickets")
async def setup_suporte(interaction: discord.Interaction):
    if interaction.user.id != ID_DONO: return
    embed = discord.Embed(title="🆘 Suporte & Resgate", description="Clique abaixo para abrir um ticket.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=TicketOpenView())
    await interaction.response.send_message("Painel configurado!", ephemeral=True)

@bot.tree.command(name="resgatar", description="Gera sua chave automaticamente")
async def resgatar(interaction: discord.Interaction, senha: str):
    if senha.strip() == SENHA_LIBERACAO:
        nova = f"PROMO-{str(uuid.uuid4())[:8].upper()}"
        dados = carregar_dados()
        if "chaves_ativas" not in dados: dados["chaves_ativas"] = []
        dados["chaves_ativas"].append(nova)
        salvar_dados(dados)
        await interaction.response.send_message(f"🔑 Sua chave é: `{nova}`", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Senha incorreta.", ephemeral=True)

@bot.tree.command(name="ativar", description="Ativa a licença Pro")
async def ativar(interaction: discord.Interaction, chave: str):
    chave_limpa = chave.strip()
    dados = carregar_dados()
    if "chaves_ativas" in dados and chave_limpa in dados["chaves_ativas"]:
        dados["servidores"][str(interaction.guild.id)] = {"usuarios": {}}
        dados["chaves_ativas"].remove(chave_limpa)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 Licença Pro ativada!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Chave `{chave_limpa}` inválida.", ephemeral=True)

bot.run(TOKEN)