import discord
from discord.ext import commands
import json, os, asyncio, uuid, pytz
from datetime import datetime
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÕES ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BR_TZ = pytz.timezone('America/Sao_Paulo')
FMT_HORA = "%Y-%m-%d %H:%M:%S"

# ⚠️ COLOQUE SEU ID MANUALMENTE AQUI
ID_DONO = 1490046139766935612 

SENHA_LIBERACAO = "PONTO_2024_PRO" 
ID_SERVIDOR_VENDAS = 1491423855334654002 
LINK_SUPORTE = "https://discord.gg/ZNHXTuKmAF" 

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
        print(f"Erro ao salvar dados: {e}")

# --- 3. LÓGICA DE PROCESSAMENTO DE SAÍDA ---
async def processar_saida(user, guild, automatico=False):
    sid, uid = str(guild.id), str(user.id)
    dados = carregar_dados()
    
    if sid not in dados["servidores"]: return
    servidor_db = dados["servidores"][sid]
    
    if uid not in servidor_db["usuarios"] or not servidor_db["usuarios"][uid].get("entrada"):
        return

    entrada_str = servidor_db["usuarios"][uid]["entrada"]
    entrada_dt = BR_TZ.localize(datetime.strptime(entrada_str, FMT_HORA))
    agora = datetime.now(BR_TZ)
    
    delta = agora - entrada_dt
    segundos_trabalhados = int(delta.total_seconds())
    
    total_antigo = servidor_db["usuarios"][uid].get("total_segundos", 0)
    servidor_db["usuarios"][uid]["total_segundos"] = total_antigo + segundos_trabalhados
    
    horas, rem = divmod(segundos_trabalhados, 3600)
    minutos, segundos = divmod(rem, 60)
    tempo_sessao = f"{horas}h {minutos}m {segundos}s"

    servidor_db["usuarios"][uid]["entrada"] = None
    salvar_dados(dados)

    embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.red())
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="🏢 Empresa/Servidor", value=f"**{guild.name}**", inline=False)
    embed.add_field(name="👤 Funcionário", value=f"**{user.display_name}**", inline=False)
    embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📌 Evento", value="Saída (Auto)" if automatico else "Saída", inline=True)
    embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
    embed.add_field(name="⏳ Tempo Total", value=f"**{tempo_sessao}**", inline=False)
    
    footer = "Jornada encerrada por inatividade no servidor" if automatico else "Registro realizado com sucesso"
    embed.set_footer(text=footer)

    try: await user.send(embed=embed)
    except: pass

# --- 4. VIEW PERSISTENTE ---
class PontoView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="persistent_ent_v10")
    async def ent(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid, uid = str(interaction.guild.id), str(interaction.user.id)
        dados = carregar_dados()

        if sid not in dados["servidores"]:
            return await interaction.response.send_message("❌ Servidor sem licença ativa.", ephemeral=True, delete_after=5)

        if not interaction.user.voice or interaction.user.voice.channel.guild.id != interaction.guild.id:
            return await interaction.response.send_message("❌ Você precisa estar em um canal de voz DESTE servidor.", ephemeral=True, delete_after=5)

        servidor_db = dados["servidores"][sid]
        if servidor_db["usuarios"].get(uid, {}).get("entrada"):
             return await interaction.response.send_message("⚠️ Você já possui uma entrada ativa.", ephemeral=True, delete_after=5)

        agora = datetime.now(BR_TZ)
        if uid not in servidor_db["usuarios"]: servidor_db["usuarios"][uid] = {"total_segundos": 0}
        servidor_db["usuarios"][uid]["entrada"] = agora.strftime(FMT_HORA)
        salvar_dados(dados)

        # --- ENVIO DO COMPROVANTE NA DM (RESTAURADO) ---
        embed_dm = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.green())
        if interaction.guild.icon: embed_dm.set_thumbnail(url=interaction.guild.icon.url)
        embed_dm.add_field(name="🏢 Empresa/Servidor", value=f"**{interaction.guild.name}**", inline=False)
        embed_dm.add_field(name="👤 Funcionário", value=f"**{interaction.user.display_name}**", inline=False)
        embed_dm.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed_dm.add_field(name="📌 Evento", value="Entrada", inline=True)
        embed_dm.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed_dm.set_footer(text="Registro realizado com sucesso")

        try:
            await interaction.user.send(embed=embed_dm)
            await interaction.response.send_message("✅ Entrada registrada e enviada na DM!", ephemeral=True, delete_after=5)
        except:
            await interaction.response.send_message("✅ Entrada registrada! (Abra sua DM para receber o comprovante)", ephemeral=True, delete_after=5)

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="persistent_sai_v10")
    async def sai(self, interaction: discord.Interaction, button: discord.ui.Button):
        mid = f"{interaction.guild.id}-{interaction.user.id}"
        if mid in self.bot.monitoramento_voz:
            self.bot.monitoramento_voz[mid].cancel()
            del self.bot.monitoramento_voz[mid]

        await interaction.response.send_message("✅ Saída processada.", ephemeral=True, delete_after=5)
        await processar_saida(interaction.user, interaction.guild)

    @discord.ui.button(label="Calcular Horas", style=discord.ButtonStyle.secondary, custom_id="persistent_calc_v10")
    async def calc(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid, uid = str(interaction.guild.id), str(interaction.user.id)
        dados = carregar_dados()
        
        if sid not in dados["servidores"] or uid not in dados["servidores"][sid]["usuarios"]:
            return await interaction.response.send_message("❌ Sem horas registradas.", ephemeral=True, delete_after=5)

        total_segundos = dados["servidores"][sid]["usuarios"][uid].get("total_segundos", 0)
        horas, rem = divmod(total_segundos, 3600)
        minutos, segundos = divmod(rem, 60)
        tempo_formatado = f"**{horas} horas, {minutos} minutos e {segundos} segundos**"
        
        embed = discord.Embed(title="📊 Relatório de Horas", color=discord.Color.blue())
        if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.add_field(name="🏢 Empresa", value=f"**{interaction.guild.name}**", inline=False)
        embed.add_field(name="👤 Funcionário", value=f"**{interaction.user.display_name}**", inline=False)
        embed.add_field(name="⏳ Total Acumulado", value=tempo_formatado, inline=False)
        embed.set_footer(text="Cálculo exato baseado em todos os registros.")

        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("✅ Relatório enviado na DM!", ephemeral=True, delete_after=5)
        except:
            await interaction.response.send_message("❌ Erro ao enviar DM. Verifique suas configurações de privacidade.", ephemeral=True, delete_after=5)

# --- 5. CLASSE DO BOT ---
class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.monitoramento_voz = {}

    async def setup_hook(self):
        self.add_view(PontoView(self))
        await self.tree.sync()
        print("✅ Bot Online e Comandos Sincronizados.")

    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        sid, uid = str(member.guild.id), str(member.id)
        mid = f"{sid}-{uid}"
        
        if before.channel and before.channel.guild.id == member.guild.id:
            if not after.channel or after.channel.guild.id != member.guild.id:
                dados = carregar_dados()
                if sid in dados["servidores"] and uid in dados["servidores"][sid]["usuarios"]:
                    if dados["servidores"][sid]["usuarios"][uid].get("entrada"):
                        if mid in self.monitoramento_voz: self.monitoramento_voz[mid].cancel()
                        self.monitoramento_voz[mid] = asyncio.create_task(self.aguardar_retorno(member, member.guild))
        
        if after.channel and after.channel.guild.id == member.guild.id:
            if mid in self.monitoramento_voz:
                self.monitoramento_voz[mid].cancel()
                del self.monitoramento_voz[mid]

    async def aguardar_retorno(self, member, guild):
        try:
            await asyncio.sleep(300) # 5 minutos
            await processar_saida(member, guild, automatico=True)
            mid = f"{guild.id}-{member.id}"
            if mid in self.monitoramento_voz: del self.monitoramento_voz[mid]
        except asyncio.CancelledError: pass

bot = PontoBot()

@bot.tree.command(name="ponto", description="Abre o painel de ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Central de Ponto", description="Use os botões abaixo para registrar sua jornada.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView(bot))

@bot.tree.command(name="ativar", description="Ativa licença")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        dados["servidores"][str(interaction.guild.id)] = {"usuarios": {}, "nome": interaction.guild.name}
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 Licença Ativada!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Chave Inválida.", ephemeral=True)

bot.run(TOKEN)