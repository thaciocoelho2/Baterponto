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
FMT_HORA = "%Y-%m-%d %H:%M:%S"

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
        await interaction.response.send_message("Encerrando atendimento em 3 segundos...", delete_after=3)
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
        await interaction.response.send_message(f"Ticket criado: {canal.mention}", ephemeral=True, delete_after=8)

class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="btn_ent")
    async def ent(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        dados = carregar_dados()

        if sid not in dados["servidores"]:
            v_venda = discord.ui.View()
            v_venda.add_item(discord.ui.Button(label="Assinar Agora", url=LINK_PAGAMENTO))
            return await interaction.response.send_message("🔒 Servidor sem assinatura ativa.", view=v_venda, ephemeral=True)

        servidor = dados["servidores"][sid]
        if uid in servidor["usuarios"] and servidor["usuarios"][uid].get("entrada"):
             return await interaction.response.send_message("⚠️ Você já tem uma entrada ativa!", ephemeral=True, delete_after=8)

        agora = datetime.now(BR_TZ)
        if uid not in servidor["usuarios"]: servidor["usuarios"][uid] = {}
        servidor["usuarios"][uid]["entrada"] = agora.strftime(FMT_HORA)
        salvar_dados(dados)

        embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.green())
        embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="📌 Evento", value="Entrada", inline=True)
        embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed.set_footer(text=f"Hoje às {agora.strftime('%H:%M')}")
        
        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message(f"✅ Entrada registrada! Comprovante enviado na sua DM.", ephemeral=True, delete_after=8)
        except discord.Forbidden:
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=8)

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="btn_sai")
    async def sai(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        dados = carregar_dados()

        if sid not in dados["servidores"]:
             return await interaction.response.send_message("🔒 Servidor sem assinatura.", ephemeral=True)

        servidor = dados["servidores"][sid]
        if uid not in servidor["usuarios"] or not servidor["usuarios"][uid].get("entrada"):
             return await interaction.response.send_message("⚠️ Você precisa registrar entrada primeiro.", ephemeral=True, delete_after=8)

        entrada_str = servidor["usuarios"][uid]["entrada"]
        entrada_dt = BR_TZ.localize(datetime.strptime(entrada_str, FMT_HORA))
        agora = datetime.now(BR_TZ)
        
        delta = agora - entrada_dt
        horas, rem = divmod(delta.seconds, 3600)
        minutos, segundos = divmod(rem, 60)
        tempo_total = f"{horas}h {minutos}m {segundos}s"

        servidor["usuarios"][uid]["entrada"] = None
        salvar_dados(dados)

        embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.red())
        embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="📌 Evento", value="Saída", inline=True)
        embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed.add_field(name="⏳ Tempo Total", value=f"**{tempo_total}**", inline=False)
        embed.set_footer(text=f"Hoje às {agora.strftime('%H:%M')}")

        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message(f"✅ Saída registrada! Comprovante enviado na sua DM.", ephemeral=True, delete_after=8)
        except discord.Forbidden:
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=8)

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
    embed = discord.Embed(title="🗓️ Central de Ponto", description="Use os botões abaixo para registrar sua jornada.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView())

@bot.tree.command(name="setup_suporte", description="Configura os tickets")
async def setup_suporte(interaction: discord.Interaction):
    if interaction.user.id != ID_DONO: return
    embed = discord.Embed(title="🆘 Suporte & Resgate", description="Clique abaixo para abrir um ticket.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=TicketOpenView())
    await interaction.response.send_message("Painel configurado!", ephemeral=True, delete_after=8)

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
        await interaction.response.send_message("❌ Senha incorreta.", ephemeral=True, delete_after=8)

@bot.tree.command(name="ativar", description="Ativa a licença Pro")
async def ativar(interaction: discord.Interaction, chave: str):
    chave_limpa = chave.strip()
    dados = carregar_dados()
    if "chaves_ativas" in dados and chave_limpa in dados["chaves_ativas"]:
        if str(interaction.guild.id) not in dados["servidores"]:
            dados["servidores"][str(interaction.guild.id)] = {"usuarios": {}}
        dados["chaves_ativas"].remove(chave_limpa)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 Licença Pro ativada!", ephemeral=True, delete_after=8)
    else:
        await interaction.response.send_message(f"❌ Chave `{chave_limpa}` inválida.", ephemeral=True, delete_after=8)

bot.run(TOKEN)