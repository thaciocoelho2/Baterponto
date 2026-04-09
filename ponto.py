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

# ⚠️ COLOQUE SEU ID AQUI PARA LIBERAR OS COMANDOS DE DONO
ID_DONO = 1490046139766935612 
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
    
    footer = "Jornada encerrada por inatividade" if automatico else "Registro realizado com sucesso"
    embed.set_footer(text=footer)

    try: await user.send(embed=embed)
    except: pass

# --- 4. VIEW PERSISTENTE ---
class PontoView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="persistent_ent_v2")
    async def ent(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Você precisa estar em um canal de voz.", ephemeral=True, delete_after=5)

        sid, uid = str(interaction.guild.id), str(interaction.user.id)
        dados = carregar_dados()

        if sid not in dados["servidores"]:
            return await interaction.response.send_message("🔒 Servidor sem assinatura ativa.", ephemeral=True, delete_after=5)

        servidor_db = dados["servidores"][sid]
        if servidor_db["usuarios"].get(uid, {}).get("entrada"):
             return await interaction.response.send_message("⚠️ Você já possui uma entrada ativa.", ephemeral=True, delete_after=5)

        agora = datetime.now(BR_TZ)
        if uid not in servidor_db["usuarios"]: servidor_db["usuarios"][uid] = {"total_segundos": 0}
        servidor_db["usuarios"][uid]["entrada"] = agora.strftime(FMT_HORA)
        servidor_db["nome"] = interaction.guild.name
        salvar_dados(dados)

        embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.green())
        if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.add_field(name="🏢 Empresa/Servidor", value=f"**{interaction.guild.name}**", inline=False)
        embed.add_field(name="👤 Funcionário", value=f"**{interaction.user.display_name}**", inline=False)
        embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="📌 Evento", value="Entrada", inline=True)
        embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed.set_footer(text="Registro realizado com sucesso")
        
        try: await interaction.user.send(embed=embed)
        except: pass
        await interaction.response.send_message("✅ Entrada registrada!", ephemeral=True, delete_after=5)

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="persistent_sai_v2")
    async def sai(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid in self.bot.monitoramento_voz:
            self.bot.monitoramento_voz[uid].cancel()
            del self.bot.monitoramento_voz[uid]

        await interaction.response.send_message("✅ Saída processada.", ephemeral=True, delete_after=5)
        await processar_saida(interaction.user, interaction.guild)

    @discord.ui.button(label="Calcular Horas", style=discord.ButtonStyle.secondary, custom_id="persistent_calc_v2")
    async def calc(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid, uid = str(interaction.guild.id), str(interaction.user.id)
        dados = carregar_dados()
        
        if sid not in dados["servidores"] or uid not in dados["servidores"][sid]["usuarios"]:
            return await interaction.response.send_message("❌ Você ainda não possui horas registradas.", ephemeral=True, delete_after=5)

        total_segundos = dados["servidores"][sid]["usuarios"][uid].get("total_segundos", 0)
        horas, rem = divmod(total_segundos, 3600)
        minutos, segundos = divmod(rem, 60)
        
        embed = discord.Embed(title="📊 Relatório de Horas", color=discord.Color.blue())
        if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.add_field(name="🏢 Empresa", value=f"**{interaction.guild.name}**", inline=False)
        embed.add_field(name="👤 Funcionário", value=f"**{interaction.user.display_name}**", inline=False)
        embed.add_field(name="⏳ Total Acumulado", value=f"**{horas} horas, {minutos} minutos e {segundos} segundos**", inline=False)
        embed.set_footer(text="Cálculo exato baseado em todos os registros.")

        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("✅ Relatório enviado na DM!", ephemeral=True, delete_after=5)
        except:
            await interaction.response.send_message("❌ Abra sua DM para receber o relatório.", ephemeral=True, delete_after=5)

# --- 5. CLASSE DO BOT ---
class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.monitoramento_voz = {}

    async def setup_hook(self):
        self.add_view(PontoView(self))
        await self.tree.sync()
        print(f"✅ Bot Online e Views Persistentes carregadas.")

    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        sid, uid = str(member.guild.id), str(member.id)
        if before.channel and not after.channel:
            dados = carregar_dados()
            if sid in dados["servidores"] and uid in dados["servidores"][sid]["usuarios"]:
                if dados["servidores"][sid]["usuarios"][uid].get("entrada"):
                    if uid in self.monitoramento_voz: self.monitoramento_voz[uid].cancel()
                    self.monitoramento_voz[uid] = asyncio.create_task(self.aguardar_retorno(member, member.guild))
        if not before.channel and after.channel:
            if uid in self.monitoramento_voz:
                self.monitoramento_voz[uid].cancel()
                del self.monitoramento_voz[uid]

    async def aguardar_retorno(self, member, guild):
        try:
            await asyncio.sleep(300) 
            await processar_saida(member, guild, automatico=True)
            if str(member.id) in self.monitoramento_voz: del self.monitoramento_voz[str(member.id)]
        except asyncio.CancelledError: pass

bot = PontoBot()

# --- 6. COMANDOS ---

@bot.tree.command(name="ponto", description="Abre o painel de ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Central de Ponto", description="Use os botões abaixo para registrar sua jornada.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView(bot))

@bot.tree.command(name="resgatar", description="Gera chave (Apenas Dono)")
async def resgatar(interaction: discord.Interaction, senha: str):
    if senha.strip() == SENHA_LIBERACAO:
        nova = f"PROMO-{str(uuid.uuid4())[:8].upper()}"
        dados = carregar_dados()
        dados["chaves_ativas"].append(nova)
        salvar_dados(dados)
        await interaction.response.send_message(f"🔑 Chave: `{nova}`", ephemeral=True)
    else: await interaction.response.send_message("❌ Senha incorreta.", ephemeral=True)

@bot.tree.command(name="ativar", description="Ativa licença")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        dados["servidores"][str(interaction.guild.id)] = {"usuarios": {}, "nome": interaction.guild.name}
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 Licença Ativada!", ephemeral=True)
    else: await interaction.response.send_message("❌ Chave inválida.", ephemeral=True)

@bot.tree.command(name="listar_servidores", description="Lista servidores ativos (Apenas Dono)")
async def listar_servidores(interaction: discord.Interaction):
    if interaction.user.id != ID_DONO:
        return await interaction.response.send_message("❌ Acesso negado.", ephemeral=True)
    dados = carregar_dados()
    lista = "\n".join([f"🏢 **{v.get('nome', 'N/A')}** | ID: `{k}`" for k, v in dados["servidores"].items()])
    await interaction.response.send_message(f"📊 **Servidores Ativos:**\n{lista if lista else 'Nenhum'}", ephemeral=True)

@bot.tree.command(name="suspender", description="Remove licença de um servidor (Apenas Dono)")
async def suspender(interaction: discord.Interaction, id_servidor: str):
    if interaction.user.id != ID_DONO:
        return await interaction.response.send_message("❌ Acesso negado.", ephemeral=True)
    dados = carregar_dados()
    if id_servidor in dados["servidores"]:
        del dados["servidores"][id_servidor]
        salvar_dados(dados)
        await interaction.response.send_message(f"🚫 Servidor `{id_servidor}` removido do sistema.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Servidor não encontrado.", ephemeral=True)

bot.run(TOKEN)