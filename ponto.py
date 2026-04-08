import discord
from discord.ext import commands
from discord import app_commands
import json, os, asyncio, uuid, pytz
from datetime import datetime
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÕES ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BR_TZ = pytz.timezone('America/Sao_Paulo') # Fuso horário do Brasil
FMT_HORA = "%Y-%m-%d %H:%M:%S"

# ⚠️ AJUSTE SEUS DADOS AQUI
ID_DONO = 123456789012345678  # Seu ID numérico do Discord
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
    
    if uid not in servidor_db["usuarios"] or not servidor_db["usuarios"][uid].get("entrada"):
        return

    entrada_str = servidor_db["usuarios"][uid]["entrada"]
    entrada_dt = BR_TZ.localize(datetime.strptime(entrada_str, FMT_HORA))
    agora = datetime.now(BR_TZ)
    
    delta = agora - entrada_dt
    horas, rem = divmod(delta.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    tempo_total = f"{horas}h {minutos}m {segundos}s"

    # Limpa o banco antes de enviar para evitar duplicidade
    servidor_db["usuarios"][uid]["entrada"] = None
    salvar_dados(dados)

    # Cria o Embed de Saída (Restaurado e Completo)
    titulo = "📄 Comprovante de Ponto (Encerrado)" if automatico else "📄 Comprovante de Ponto"
    embed = discord.Embed(title=titulo, color=discord.Color.red())
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="🏢 Empresa/Servidor", value=f"**{guild.name}**", inline=False)
    embed.add_field(name="👤 Funcionário", value=f"**{user.display_name}**", inline=False)
    embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📌 Evento", value="Saída (Auto)" if automatico else "Saída", inline=True)
    embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
    embed.add_field(name="⏳ Tempo Total", value=f"**{tempo_total}**", inline=False)
    embed.set_footer(text="Jornada encerrada por inatividade" if automatico else "Registro realizado com sucesso")

    try:
        await user.send(embed=embed)
    except:
        pass

# --- 4. INTERFACES (VIEWS) ---
class PontoView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="btn_ent_restaurado_v1")
    async def ent(self, interaction: discord.Interaction, button: discord.ui.Button):
        # REGRA: Verificar se está em canal de voz
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("❌ **Acesso Negado:** Você precisa estar em um canal de voz deste servidor para iniciar o ponto.", ephemeral=True, delete_after=10)

        guild_name = str(interaction.guild.name)
        user_name = interaction.user.display_name
        sid, uid = str(interaction.guild.id), str(interaction.user.id)
        dados = carregar_dados()

        # 1. Verificação de Licença
        if sid not in dados["servidores"]:
            return await interaction.response.send_message("🔒 Servidor sem assinatura ativa.", ephemeral=True)

        servidor_db = dados["servidores"][sid]
        # 2. Lógica de Entrada (Proteção contra clique duplo)
        if uid in servidor_db["usuarios"] and servidor_db["usuarios"][uid].get("entrada"):
             return await interaction.response.send_message("⚠️ Você já tem uma entrada ativa! Registre a saída primeiro.", ephemeral=True, delete_after=8)

        # 3. Registrar Entrada
        agora = datetime.now(BR_TZ)
        if uid not in servidor_db["usuarios"]: servidor_db["usuarios"][uid] = {}
        servidor_db["usuarios"][uid]["entrada"] = agora.strftime(FMT_HORA)
        # Salva o nome do servidor no momento da ativação para facilitar sua listagem depois
        servidor_db["nome"] = interaction.guild.name 
        salvar_dados(dados)

        # --- NOVA ESTRUTURA DO COMPROVANTE DE ENTRADA (RESTAURADA IGUAL IMAGEM 13) ---
        embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.green())
        
        # Adiciona o ícone do servidor no canto (thumbnail) se existir (Logo SICTEC)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.add_field(name="🏢 Empresa/Servidor", value=f"**{guild_name}**", inline=False)
        embed.add_field(name="👤 Funcionário", value=f"**{user_name}**", inline=False)
        embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True) # Campo restaurado
        embed.add_field(name="📌 Evento", value="Entrada", inline=True) # Campo restaurado
        embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed.set_footer(text="Registro realizado com sucesso")
        
        # 4. Enviar DM e responder efemeramente (auto-delete 8s)
        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message(f"✅ Entrada registrada! Comprovante enviado na sua DM.", ephemeral=True, delete_after=8)
        except discord.Forbidden:
            # Se a DM estiver fechada, envia o embed aqui efemeramente
            embed.set_footer(text=f"⚠️ ID do Servidor: {sid} | Abra sua DM para receber o comprovante privado.")
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=8)

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="btn_sai_restaurado_v1")
    async def sai(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        # IMPORTANTE: Cancela timer de 5min se clicar manualmente
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
        # Torna as views persistentes (continuam funcionando após reiniciar)
        self.add_view(PontoView(self))
        await self.tree.sync()
        print(f"✅ Bot operacional: {self.user}")

    # REGRA 2: Monitoramento de saída da Call (5 minutos)
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        sid, uid = str(member.guild.id), str(member.id)
        
        # Se saiu de um canal e não entrou em nenhum outro do servidor
        if before.channel and not after.channel:
            dados = carregar_dados()
            # Verifica se o usuário tem um ponto ativo
            if sid in dados["servidores"] and uid in dados["servidores"][sid]["usuarios"]:
                if dados["servidores"][sid]["usuarios"][uid].get("entrada"):
                    # Cancela tarefa anterior se existir
                    if uid in self.monitoramento_voz: self.monitoramento_voz[uid].cancel()
                    # Inicia contagem de 5 minutos (300 segundos)
                    task = asyncio.create_task(self.aguardar_retorno(member, member.guild))
                    self.monitoramento_voz[uid] = task

        # Se voltou para qualquer canal de voz, cancela o encerramento automático
        if not before.channel and after.channel:
            if uid in self.monitoramento_voz:
                self.monitoramento_voz[uid].cancel()
                del self.monitoramento_voz[uid]

    async def aguardar_retorno(self, member, guild):
        try:
            await asyncio.sleep(300) # 5 minutos
            # Se chegou aqui, o usuário não voltou. Encerra o ponto.
            await processar_saida(member, guild, automatico=True)
            if str(member.id) in self.monitoramento_voz: del self.monitoramento_voz[str(member.id)]
        except asyncio.CancelledError: pass

bot = PontoBot()

# --- 6. COMANDOS ---
@bot.tree.command(name="ponto", description="Abre o painel de registro de ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Central de Ponto", description="Registre sua entrada ou saída pelos botões abaixo. **Obrigatório estar em canal de voz para entrada.**", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView(bot))

@bot.tree.command(name="resgatar", description="Gera sua chave (Dono)")
async def resgatar(interaction: discord.Interaction, senha: str):
    if senha.strip() == SENHA_LIBERACAO:
        nova = f"PROMO-{str(uuid.uuid4())[:8].upper()}"
        dados = carregar_dados()
        dados["chaves_ativas"].append(nova)
        salvar_dados(dados)
        await interaction.response.send_message(f"🔑 **Chave Gerada!**\nSua chave única de ativação é: `{nova}`\nCopie e use o comando `/ativar` no servidor do cliente.", ephemeral=True)
    else: await interaction.response.send_message("❌ Senha incorreta.", ephemeral=True)

@bot.tree.command(name="ativar", description="Ativa licença no servidor")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        sid = str(interaction.guild.id)
        dados["servidores"][sid] = {"usuarios": {}, "nome": interaction.guild.name}
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 **Sucesso!** Licença Pro ativada neste servidor.", ephemeral=True)
    else: await interaction.response.send_message("❌ Chave inválida ou já utilizada.", ephemeral=True)

# --- 7. COMANDOS DE GESTÃO (APENAS DONO) ---
@bot.tree.command(name="listar_servidores", description="Lista servidores ativos (Dono)")
async def listar_servidores(interaction: discord.Interaction):
    if interaction.user.id != ID_DONO: return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    dados = carregar_dados()
    if not dados["servidores"]: return await interaction.response.send_message("Nenhum servidor ativo.", ephemeral=True)
    lista = ""
    for sid, info in dados["servidores"].items():
        nome = info.get("nome", "Desconhecido")
        lista += f"🏢 **Nome:** {nome} | **ID:** `{sid}`\n"
    embed = discord.Embed(title="📊 Servidores Ativos", description=lista, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="suspender", description="Remove licença (Dono)")
async def suspender(interaction: discord.Interaction, id_servidor: str):
    if interaction.user.id != ID_DONO: return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    dados = carregar_dados()
    if id_servidor in dados["servidores"]:
        nome = dados["servidores"][id_servidor].get("nome", id_servidor)
        del dados["servidores"][id_servidor]
        salvar_dados(dados)
        await interaction.response.send_message(f"🚫 Licença de **{nome}** (`{id_servidor}`) removida!", ephemeral=True)
    else: await interaction.response.send_message("❌ ID não encontrado.", ephemeral=True)

bot.run(TOKEN)