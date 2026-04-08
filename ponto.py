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

ID_DONO = 123456789012345678  
LINK_PAGAMENTO = "https://seu-link-aqui.com" 
SENHA_LIBERACAO = "PONTO_2024_PRO" 

# --- 2. BANCO DE DADOS ---
def carregar_dados():
    try:
        if not os.path.exists('database.json'):
            return {"servidores": {}, "chaves_ativas": []}
        with open('database.json', 'r', encoding='utf-8') as f:
            content = f.read()
            return json.loads(content) if (content and content.strip()) else {"servidores": {}, "chaves_ativas": []}
    except Exception:
        return {"servidores": {}, "chaves_ativas": []}

def salvar_dados(dados):
    try:
        with open('database.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar: {e}")

# --- 3. LÓGICA DE PROCESSAMENTO DE SAÍDA ---
async def processar_saida(user, guild, automatico=False):
    sid, uid = str(guild.id), str(user.id)
    dados = carregar_dados()
    
    if sid not in dados["servidores"]: return
    servidor_db = dados["servidores"][sid]
    
    # TRAVA DE SEGURANÇA: Se não houver entrada ativa no JSON, cancela o envio
    if uid not in servidor_db["usuarios"] or not servidor_db["usuarios"][uid].get("entrada"):
        return

    entrada_str = servidor_db["usuarios"][uid]["entrada"]
    entrada_dt = BR_TZ.localize(datetime.strptime(entrada_str, FMT_HORA))
    agora = datetime.now(BR_TZ)
    
    delta = agora - entrada_dt
    horas, rem = divmod(delta.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    tempo_total = f"{horas}h {minutos}m {segundos}s"

    # LIMPA O BANCO ANTES DE ENVIAR (Evita duplicidade se houver lag)
    servidor_db["usuarios"][uid]["entrada"] = None
    salvar_dados(dados)

    embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.red())
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="🏢 Empresa/Servidor", value=f"**{guild.name}**", inline=False)
    embed.add_field(name="👤 Funcionário", value=f"**{user.display_name}**", inline=False)
    embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📌 Evento", value="Saída (Auto)" if automatico else "Saída", inline=True)
    embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
    embed.add_field(name="⏳ Tempo Total", value=f"**{tempo_total}**", inline=False)
    
    footer_text = "Jornada encerrada por inatividade" if automatico else "Registro realizado com sucesso"
    embed.set_footer(text=footer_text)

    try:
        await user.send(embed=embed)
    except:
        pass

# --- 4. INTERFACES (VIEWS) ---
class PontoView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance # Passamos a instância do bot para gerenciar o monitoramento

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="btn_ent_ponto_v2")
    async def ent(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ **Acesso Negado:** Você precisa estar em um canal de voz para iniciar o ponto.", 
                ephemeral=True, delete_after=10
            )

        sid, uid = str(interaction.guild.id), str(interaction.user.id)
        dados = carregar_dados()

        if sid not in dados["servidores"]:
            return await interaction.response.send_message("🔒 Servidor sem assinatura ativa.", ephemeral=True)

        servidor_db = dados["servidores"][sid]
        if uid in servidor_db["usuarios"] and servidor_db["usuarios"][uid].get("entrada"):
             return await interaction.response.send_message("⚠️ Você já possui uma entrada ativa.", ephemeral=True, delete_after=8)

        agora = datetime.now(BR_TZ)
        if uid not in servidor_db["usuarios"]: servidor_db["usuarios"][uid] = {}
        servidor_db["usuarios"][uid]["entrada"] = agora.strftime(FMT_HORA)
        salvar_dados(dados)

        embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.green())
        if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.add_field(name="🏢 Empresa/Servidor", value=f"**{interaction.guild.name}**", inline=False)
        embed.add_field(name="👤 Funcionário", value=f"**{interaction.user.display_name}**", inline=False)
        embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="📌 Evento", value="Entrada", inline=True)
        embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed.set_footer(text="Registro realizado com sucesso")
        
        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message(f"✅ Entrada registrada!", ephemeral=True, delete_after=8)
        except:
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=8)

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="btn_sai_ponto_v2")
    async def sai(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        
        # IMPORTANTE: Se o usuário bater a saída manualmente, cancelamos o timer de 5min imediatamente
        if uid in self.bot.monitoramento_voz:
            self.bot.monitoramento_voz[uid].cancel()
            del self.bot.monitoramento_voz[uid]

        await interaction.response.defer(ephemeral=True)
        await processar_saida(interaction.user, interaction.guild)
        await interaction.followup.send("✅ Saída processada.", ephemeral=True)

# --- 5. CLASSE DO BOT ---
class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.monitoramento_voz = {}

    async def setup_hook(self):
        # Passamos 'self' para a View para que ela possa cancelar tarefas de voz
        self.add_view(PontoView(self))
        await self.tree.sync()

    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        sid, uid = str(member.guild.id), str(member.id)
        
        # Saiu da call
        if before.channel and not after.channel:
            dados = carregar_dados()
            if sid in dados["servidores"] and uid in dados["servidores"][sid]["usuarios"]:
                if dados["servidores"][sid]["usuarios"][uid].get("entrada"):
                    if uid in self.monitoramento_voz:
                        self.monitoramento_voz[uid].cancel()
                    
                    task = asyncio.create_task(self.aguardar_retorno(member, member.guild))
                    self.monitoramento_voz[uid] = task

        # Voltou para a call (Cancela o encerramento automático)
        if not before.channel and after.channel:
            if uid in self.monitoramento_voz:
                self.monitoramento_voz[uid].cancel()
                del self.monitoramento_voz[uid]

    async def aguardar_retorno(self, member, guild):
        try:
            await asyncio.sleep(300) # 5 minutos
            await processar_saida(member, guild, automatico=True)
            uid = str(member.id)
            if uid in self.monitoramento_voz:
                del self.monitoramento_voz[uid]
        except asyncio.CancelledError:
            pass

bot = PontoBot()

# --- 6. COMANDOS ---
@bot.tree.command(name="ponto", description="Abre o painel de ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Central de Ponto", description="Use os botões abaixo para registrar sua jornada.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView(bot))

# [Comandos 'resgatar' e 'ativar' permanecem iguais...]
@bot.tree.command(name="resgatar", description="Gera sua chave")
async def resgatar(interaction: discord.Interaction, senha: str):
    if senha.strip() == SENHA_LIBERACAO:
        nova = f"PROMO-{str(uuid.uuid4())[:8].upper()}"
        dados = carregar_dados()
        if "chaves_ativas" not in dados: dados["chaves_ativas"] = []
        dados["chaves_ativas"].append(nova)
        salvar_dados(dados)
        await interaction.response.send_message(f"🔑 Chave: `{nova}`", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Senha incorreta.", ephemeral=True, delete_after=8)

@bot.tree.command(name="ativar", description="Ativa licença")
async def ativar(interaction: discord.Interaction, chave: str):
    chave_limpa = chave.strip()
    dados = carregar_dados()
    if "chaves_ativas" in dados and chave_limpa in dados["chaves_ativas"]:
        if str(interaction.guild.id) not in dados["servidores"]:
            dados["servidores"][str(interaction.guild.id)] = {"usuarios": {}}
        dados["chaves_ativas"].remove(chave_limpa)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 Licença Ativada!", ephemeral=True, delete_after=8)
    else:
        await interaction.response.send_message(f"❌ Chave inválida.", ephemeral=True, delete_after=8)

bot.run(TOKEN)