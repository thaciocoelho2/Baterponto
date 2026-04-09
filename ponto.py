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

# --- 2. BANCO DE DADOS (REVISADO PARA ESTABILIDADE) ---
def carregar_dados():
    if not os.path.exists('database.json'):
        dados_iniciais = {"servidores": {}, "chaves_ativas": []}
        salvar_dados(dados_iniciais)
        return dados_iniciais
    try:
        with open('database.json', 'r', encoding='utf-8') as f:
            conteudo = f.read()
            if not conteudo.strip():
                return {"servidores": {}, "chaves_ativas": []}
            return json.loads(conteudo)
    except (json.JSONDecodeError, Exception):
        return {"servidores": {}, "chaves_ativas": []}

def salvar_dados(dados):
    try:
        with open('database.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro crítico ao salvar: {e}")

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
    embed.set_footer(text="Jornada encerrada por inatividade" if automatico else "Registro realizado com sucesso")

    try: await user.send(embed=embed)
    except: pass

# --- 4. VIEW PERSISTENTE (IDs ATUALIZADOS V13) ---
class PontoView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="ponto_ent_v13")
    async def ent(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        dados = carregar_dados()

        # Validação robusta de licença
        if sid not in dados["servidores"]:
            embed_venda = discord.Embed(
                title="🔒 Licença Não Encontrada",
                description=f"Este servidor (**{interaction.guild.name}**) não possui uma licença ativa no sistema.\n\nPara ativar, use `/ativar` com uma chave válida ou entre em contato:\n[Suporte aqui]({LINK_SUPORTE})",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_venda, ephemeral=True)

        # Validação de Voz (No servidor correto)
        if not interaction.user.voice or interaction.user.voice.channel.guild.id != interaction.guild.id:
            return await interaction.response.send_message("❌ Você precisa estar em um canal de voz DESTE servidor para bater o ponto.", ephemeral=True)

        servidor_db = dados["servidores"][sid]
        if servidor_db["usuarios"].get(uid, {}).get("entrada"):
             return await interaction.response.send_message("⚠️ Você já possui uma entrada ativa. Finalize-a primeiro.", ephemeral=True)

        agora = datetime.now(BR_TZ)
        if uid not in servidor_db["usuarios"]: servidor_db["usuarios"][uid] = {"total_segundos": 0}
        servidor_db["usuarios"][uid]["entrada"] = agora.strftime(FMT_HORA)
        salvar_dados(dados)

        # Envio de Comprovante DM
        embed_dm = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.green())
        if interaction.guild.icon: embed_dm.set_thumbnail(url=interaction.guild.icon.url)
        embed_dm.add_field(name="🏢 Empresa/Servidor", value=f"**{interaction.guild.name}**", inline=False)
        embed_dm.add_field(name="👤 Funcionário", value=f"**{interaction.user.display_name}**", inline=False)
        embed_dm.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed_dm.add_field(name="📌 Evento", value="Entrada", inline=True)
        embed_dm.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed_dm.set_footer(text="Bata sua saída ao terminar o serviço.")

        try:
            await interaction.user.send(embed=embed_dm)
            await interaction.response.send_message("✅ Entrada registrada! Verifique sua DM.", ephemeral=True)
        except:
            await interaction.response.send_message("✅ Entrada registrada! (DM bloqueada)", ephemeral=True)

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="ponto_sai_v13")
    async def sai(self, interaction: discord.Interaction, button: discord.ui.Button):
        mid = f"{interaction.guild.id}-{interaction.user.id}"
        if mid in self.bot.monitoramento_voz:
            self.bot.monitoramento_voz[mid].cancel()
            del self.bot.monitoramento_voz[mid]

        await interaction.response.send_message("✅ Saída processada com sucesso.", ephemeral=True)
        await processar_saida(interaction.user, interaction.guild)

    @discord.ui.button(label="Calcular Horas", style=discord.ButtonStyle.secondary, custom_id="ponto_calc_v13")
    async def calc(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid, uid = str(interaction.guild.id), str(interaction.user.id)
        dados = carregar_dados()
        
        if sid not in dados["servidores"] or uid not in dados["servidores"][sid]["usuarios"]:
            return await interaction.response.send_message("❌ Você ainda não possui registros de tempo neste servidor.", ephemeral=True)

        total_segundos = dados["servidores"][sid]["usuarios"][uid].get("total_segundos", 0)
        horas, rem = divmod(total_segundos, 3600)
        minutos, segundos = divmod(rem, 60)
        
        embed = discord.Embed(title="📊 Relatório de Horas", color=discord.Color.blue())
        embed.add_field(name="👤 Funcionário", value=f"**{interaction.user.display_name}**", inline=False)
        embed.add_field(name="⏳ Total Acumulado", value=f"**{horas} horas, {minutos} minutos e {segundos} segundos**", inline=False)
        embed.set_footer(text=f"Servidor: {interaction.guild.name}")

        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("✅ Relatório detalhado enviado na sua DM!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Não consegui enviar a DM. Verifique se suas mensagens privadas estão abertas.", ephemeral=True)

# --- 5. CLASSE DO BOT (LÓGICA DE VOZ REVISADA) ---
class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.monitoramento_voz = {}

    async def setup_hook(self):
        self.add_view(PontoView(self))
        await self.tree.sync()
        print(f"✅ Sistema de Ponto v13 - {self.user} Online")

    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        sid, uid = str(member.guild.id), str(member.id)
        mid = f"{sid}-{uid}"
        
        # Caso: Saiu da call deste servidor ou mudou para outro servidor
        if before.channel and before.channel.guild.id == member.guild.id:
            if not after.channel or after.channel.guild.id != member.guild.id:
                dados = carregar_dados()
                if sid in dados["servidores"] and uid in dados["servidores"][sid]["usuarios"]:
                    if dados["servidores"][sid]["usuarios"][uid].get("entrada"):
                        if mid in self.monitoramento_voz: self.monitoramento_voz[mid].cancel()
                        self.monitoramento_voz[mid] = asyncio.create_task(self.aguardar_retorno(member, member.guild))
        
        # Caso: Voltou para a call deste servidor
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

# --- 6. COMANDOS ADMINISTRATIVOS ---
@bot.tree.command(name="ponto", description="Abre o painel de ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Central de Ponto", description="Clique abaixo para registrar sua entrada ou saída.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView(bot))

@bot.tree.command(name="resgatar", description="Gera chave (Dono do Bot)")
async def resgatar(interaction: discord.Interaction, senha: str):
    if interaction.user.id != ID_DONO:
        return await interaction.response.send_message("❌ Apenas o desenvolvedor pode usar este comando.", ephemeral=True)
    if senha.strip() == SENHA_LIBERACAO:
        nova = f"PROMO-{str(uuid.uuid4())[:8].upper()}"
        dados = carregar_dados()
        dados["chaves_ativas"].append(nova)
        salvar_dados(dados)
        await interaction.response.send_message(f"🔑 **Chave Gerada:** `{nova}`\nEnvie para o cliente ativar.", ephemeral=True)
    else: await interaction.response.send_message("❌ Senha de liberação incorreta.", ephemeral=True)

@bot.tree.command(name="ativar", description="Ativa licença do servidor")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        sid = str(interaction.guild.id)
        dados["servidores"][sid] = {
            "usuarios": {}, 
            "nome": interaction.guild.name,
            "data_ativacao": datetime.now(BR_TZ).strftime(FMT_HORA)
        }
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message(f"🎉 **Sucesso!** O servidor **{interaction.guild.name}** foi ativado.", ephemeral=True)
    else: await interaction.response.send_message("❌ Chave inválida ou já utilizada.", ephemeral=True)

@bot.tree.command(name="listar_servidores", description="Lista servidores ativos (Dono do Bot)")
async def listar_servidores(interaction: discord.Interaction):
    if interaction.user.id != ID_DONO: return
    dados = carregar_dados()
    if not dados["servidores"]: return await interaction.response.send_message("Nenhum servidor ativo.", ephemeral=True)
    lista = "\n".join([f"🏢 **{v.get('nome', 'N/A')}** - ID: `{k}`" for k, v in dados["servidores"].items()])
    await interaction.response.send_message(f"📊 **Servidores Licenciados:**\n{lista}", ephemeral=True)

@bot.tree.command(name="suspender", description="Remove licença (Dono do Bot)")
async def suspender(interaction: discord.Interaction, id_servidor: str):
    if interaction.user.id != ID_DONO: return
    dados = carregar_dados()
    if id_servidor in dados["servidores"]:
        nome = dados["servidores"][id_servidor].get("nome", "Desconhecido")
        del dados["servidores"][id_servidor]
        salvar_dados(dados)
        await interaction.response.send_message(f"🚫 Licença do servidor **{nome}** (`{id_servidor}`) foi removida.", ephemeral=True)
    else: await interaction.response.send_message("❌ ID não encontrado na base de dados.", ephemeral=True)

bot.run(TOKEN)