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

# ID do Dono para comandos administrativos
ID_DONO = 1490046139766935612 

SENHA_LIBERACAO = "PONTO_2024_PRO" 
LINK_SUPORTE = "https://discord.gg/ZNHXTuKmAF" 

# --- 2. BANCO DE DADOS (REESCRITO PARA EVITAR ERRO DE LEITURA) ---
def carregar_dados():
    if not os.path.exists('database.json'):
        dados = {"servidores": {}, "chaves_ativas": []}
        salvar_dados(dados)
        return dados
    try:
        with open('database.json', 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return json.loads(content) if content else {"servidores": {}, "chaves_ativas": []}
    except Exception:
        return {"servidores": {}, "chaves_ativas": []}

def salvar_dados(dados):
    try:
        # Escrita segura usando arquivo temporário para evitar corrupção
        with open('database.json.tmp', 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
        os.replace('database.json.tmp', 'database.json')
    except Exception as e:
        print(f"Erro ao salvar: {e}")

# --- 3. PROCESSAMENTO DE SAÍDA ---
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
    
    servidor_db["usuarios"][uid]["total_segundos"] = servidor_db["usuarios"][uid].get("total_segundos", 0) + segundos_trabalhados
    servidor_db["usuarios"][uid]["entrada"] = None
    salvar_dados(dados)

    horas, rem = divmod(segundos_trabalhados, 3600)
    minutos, segundos = divmod(rem, 60)
    
    embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.red())
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="🏢 Empresa/Servidor", value=f"**{guild.name}**", inline=False)
    embed.add_field(name="👤 Funcionário", value=f"**{user.display_name}**", inline=False)
    embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📌 Evento", value="Saída (Automática)" if automatico else "Saída", inline=True)
    embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
    embed.add_field(name="⏳ Tempo Total", value=f"**{horas}h {minutos}m {segundos}s**", inline=False)
    embed.set_footer(text="Registro encerrado com sucesso.")

    try: await user.send(embed=embed)
    except: pass

# --- 4. VIEW DE INTERAÇÃO (FIX V14) ---
class PontoView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="v14_ent")
    async def ent(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Recarregar dados imediatamente no clique
        dados = carregar_dados()
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)

        # Verificação de licença infalível
        if sid not in dados["servidores"]:
            # Se não achou por ID, tenta buscar pelo nome no banco (Double Check)
            servidor_ativo = False
            for s_id, info in dados["servidores"].items():
                if info.get("nome") == interaction.guild.name:
                    sid = s_id
                    servidor_ativo = True
                    break
            
            if not servidor_ativo:
                embed_erro = discord.Embed(
                    title="🔒 Licença Não Encontrada",
                    description=f"O servidor **{interaction.guild.name}** precisa ser ativado.\nUse `/ativar` ou contate o [Suporte]({LINK_SUPORTE}).",
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed_erro, ephemeral=True)

        # Restante da lógica (Voz, Registro, etc)
        if not interaction.user.voice or interaction.user.voice.channel.guild.id != interaction.guild.id:
            return await interaction.response.send_message("❌ Você deve estar em um canal de voz deste servidor.", ephemeral=True)

        servidor_db = dados["servidores"][sid]
        if servidor_db["usuarios"].get(uid, {}).get("entrada"):
             return await interaction.response.send_message("⚠️ Você já tem um ponto aberto.", ephemeral=True)

        agora = datetime.now(BR_TZ)
        if uid not in servidor_db["usuarios"]: servidor_db["usuarios"][uid] = {"total_segundos": 0}
        servidor_db["usuarios"][uid]["entrada"] = agora.strftime(FMT_HORA)
        salvar_dados(dados)

        embed_dm = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.green())
        if interaction.guild.icon: embed_dm.set_thumbnail(url=interaction.guild.icon.url)
        embed_dm.add_field(name="🏢 Empresa/Servidor", value=f"**{interaction.guild.name}**", inline=False)
        embed_dm.add_field(name="👤 Funcionário", value=f"**{interaction.user.display_name}**", inline=False)
        embed_dm.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed_dm.add_field(name="📌 Evento", value="Entrada", inline=True)
        embed_dm.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        
        try:
            await interaction.user.send(embed=embed_dm)
            await interaction.response.send_message("✅ Ponto batido! Comprovante enviado na DM.", ephemeral=True)
        except:
            await interaction.response.send_message("✅ Ponto batido! (Sua DM está fechada)", ephemeral=True)

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="v14_sai")
    async def sai(self, interaction: discord.Interaction, button: discord.ui.Button):
        mid = f"{interaction.guild.id}-{interaction.user.id}"
        if mid in self.bot.monitoramento_voz:
            self.bot.monitoramento_voz[mid].cancel()
            del self.bot.monitoramento_voz[mid]

        await interaction.response.send_message("✅ Processando saída...", ephemeral=True)
        await processar_saida(interaction.user, interaction.guild)

    @discord.ui.button(label="Calcular Horas", style=discord.ButtonStyle.secondary, custom_id="v14_calc")
    async def calc(self, interaction: discord.Interaction, button: discord.ui.Button):
        dados = carregar_dados()
        sid, uid = str(interaction.guild.id), str(interaction.user.id)
        
        if sid not in dados["servidores"] or uid not in dados["servidores"][sid]["usuarios"]:
            return await interaction.response.send_message("❌ Nenhum registro encontrado.", ephemeral=True)

        total = dados["servidores"][sid]["usuarios"][uid].get("total_segundos", 0)
        h, r = divmod(total, 3600)
        m, s = divmod(r, 60)
        
        embed = discord.Embed(title="📊 Total de Horas", color=discord.Color.blue())
        embed.description = f"Seu tempo acumulado em **{interaction.guild.name}** é:\n**{h} horas, {m} minutos e {s} segundos**"
        
        try: await interaction.user.send(embed=embed); await interaction.response.send_message("✅ Enviado na DM.", ephemeral=True)
        except: await interaction.response.send_message(embed=embed, ephemeral=True)

# --- 5. CLASSE DO BOT ---
class PontoBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.monitoramento_voz = {}

    async def setup_hook(self):
        self.add_view(PontoView(self))
        await self.tree.sync()

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
            await asyncio.sleep(300)
            await processar_saida(member, guild, automatico=True)
        except asyncio.CancelledError: pass

bot = PontoBot()

# --- 6. COMANDOS ---
@bot.tree.command(name="ponto", description="Painel de Ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Central de Ponto", description="Clique abaixo para registrar sua jornada.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView(bot))

@bot.tree.command(name="ativar", description="Ativar Licença")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        sid = str(interaction.guild.id)
        dados["servidores"][sid] = {"usuarios": {}, "nome": interaction.guild.name}
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message(f"✅ **Sucesso!** Servidor **{interaction.guild.name}** ativado.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Chave inválida.", ephemeral=True)

@bot.tree.command(name="resgatar", description="Gerar Chave (Dono)")
async def resgatar(interaction: discord.Interaction, senha: str):
    if interaction.user.id != ID_DONO: return
    if senha == SENHA_LIBERACAO:
        chave = f"PRO-{str(uuid.uuid4())[:8].upper()}"
        dados = carregar_dados()
        dados["chaves_ativas"].append(chave)
        salvar_dados(dados)
        await interaction.response.send_message(f"🔑 Chave: `{chave}`", ephemeral=True)

bot.run(TOKEN)