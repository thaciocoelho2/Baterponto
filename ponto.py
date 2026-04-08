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
            # Se o arquivo estiver vazio, retorna a estrutura padrão
            return json.loads(content) if (content and content.strip()) else {"servidores": {}, "chaves_ativas": []}
    except Exception as e:
        print(f"Erro ao carregar banco: {e}")
        # Em caso de erro grave de leitura, retorna estrutura limpa para não quebrar o bot
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
        await interaction.response.send_message(f"✅ Ticket criado: {canal.mention}", ephemeral=True, delete_after=8)

class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="btn_ent")
    async def ent(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        
        # Garante que as variáveis interaction.guild e interaction.user estão disponíveis
        if not interaction.guild or not interaction.user:
            return await interaction.response.send_message("❌ Erro interno: Não consegui ler os dados do servidor ou usuário.", ephemeral=True)

        dados = carregar_dados()

        # 1. Verificação de Licença
        if sid not in dados["servidores"]:
            v_venda = discord.ui.View()
            v_venda.add_item(discord.ui.Button(label="Assinar Agora", url=LINK_PAGAMENTO))
            return await interaction.response.send_message("🔒 Servidor sem assinatura ativa.", view=v_venda, ephemeral=True)

        # 2. Lógica de Entrada (Proteção contra clique duplo)
        servidor_db = dados["servidores"][sid]
        if uid in servidor_db["usuarios"] and servidor_db["usuarios"][uid].get("entrada"):
             return await interaction.response.send_message("⚠️ Você já tem uma entrada ativa! Registre a saída primeiro.", ephemeral=True, delete_after=8)

        # 3. Registrar Entrada
        agora = datetime.now(BR_TZ)
        if uid not in servidor_db["usuarios"]: servidor_db["usuarios"][uid] = {}
        servidor_db["usuarios"][uid]["entrada"] = agora.strftime(FMT_HORA)
        salvar_dados(dados)

        # --- NOVA ESTRUTURA DO COMPROVANTE DE ENTRADA ---
        # Definimos as variáveis antes para garantir que não fiquem vazias
        nome_servidor = interaction.guild.name # Puxa o nome igual à imagem 8
        nome_usuario = interaction.user.display_name # Puxa o apelido do usuário

        embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.green())
        
        # Adiciona o ícone do servidor no canto (thumbnail) se existir
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.add_field(name="🏢 Empresa/Servidor", value=f"**{nome_servidor}**", inline=False)
        embed.add_field(name="👤 Funcionário", value=f"**{nome_usuario}**", inline=False)
        embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="📌 Evento", value="Entrada", inline=True)
        embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed.set_footer(text=f"ID do Servidor: {sid}")
        
        # 4. Enviar DM e responder efemeramente (auto-delete 8s)
        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message(f"✅ Entrada registrada! Comprovante enviado na sua DM.", ephemeral=True, delete_after=8)
        except discord.Forbidden:
            # Se a DM estiver fechada, envia o embed aqui efemeramente
            embed.set_footer(text=f"⚠️ ID do Servidor: {sid} | Abra sua DM para receber o comprovante privado.")
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=8)

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="btn_sai")
    async def sai(self, interaction: discord.Interaction, button: discord.ui.Button):
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)

        # Garante que as variáveis interaction.guild e interaction.user estão disponíveis
        if not interaction.guild or not interaction.user:
            return await interaction.response.send_message("❌ Erro interno.", ephemeral=True)

        dados = carregar_dados()

        # 1. Verificação de Licença
        if sid not in dados["servidores"]:
             return await interaction.response.send_message("🔒 Servidor sem assinatura.", ephemeral=True)

        # 2. Lógica de Saída (Proteção contra clique duplo)
        servidor_db = dados["servidores"][sid]
        if uid not in servidor_db["usuarios"] or not servidor_db["usuarios"][uid].get("entrada"):
             return await interaction.response.send_message("⚠️ Você precisa registrar entrada primeiro.", ephemeral=True, delete_after=8)

        # 3. Calcular Tempo e Registrar Saída
        entrada_str = servidor_db["usuarios"][uid]["entrada"]
        entrada_dt = BR_TZ.localize(datetime.strptime(entrada_str, FMT_HORA))
        agora = datetime.now(BR_TZ)
        
        # Cálculo do tempo total
        delta = agora - entrada_dt
        horas, rem = divmod(delta.seconds, 3600)
        minutos, segundos = divmod(rem, 60)
        tempo_total = f"{horas}h {minutos}m {segundos}s"

        # Limpar o registro de entrada ANTES de enviar para evitar reprocessamento
        servidor_db["usuarios"][uid]["entrada"] = None
        salvar_dados(dados)

        # --- NOVA ESTRUTURA DO COMPROVANTE DE SAÍDA ---
        nome_servidor = interaction.guild.name
        nome_usuario = interaction.user.display_name

        embed = discord.Embed(title="📄 Comprovante de Ponto", color=discord.Color.red())
        
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.add_field(name="🏢 Empresa/Servidor", value=f"**{nome_servidor}**", inline=False)
        embed.add_field(name="👤 Funcionário", value=f"**{nome_usuario}**", inline=False)
        embed.add_field(name="📅 Data", value=agora.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="📌 Evento", value="Saída", inline=True)
        embed.add_field(name="⏰ Horário", value=f"`{agora.strftime('%H:%M:%S')}`", inline=False)
        embed.add_field(name="⏳ Tempo Total", value=f"**{tempo_total}**", inline=False)
        embed.set_footer(text=f"ID do Servidor: {sid}")

        # 4. Enviar DM e responder efemeramente (auto-delete 8s)
        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message(f"✅ Saída registrada! Comprovante enviado na sua DM.", ephemeral=True, delete_after=8)
        except discord.Forbidden:
            embed.set_footer(text=f"⚠️ ID do Servidor: {sid} | Abra sua DM para receber o comprovante privado.")
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=8)

# --- 4. CLASSE DO BOT ---
class PontoBot(commands.Bot):
    def __init__(self):
        # Intents necessários para ler nomes de usuários e servidores
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        # Torna as views persistentes (continuam funcionando após reiniciar)
        self.add_view(TicketOpenView())
        self.add_view(TicketControlView())
        self.add_view(PontoView())
        await self.tree.sync()
        print(f"✅ Bot logado com sucesso como: {self.user}")

bot = PontoBot()

# --- 5. COMANDOS ---
@bot.tree.command(name="ponto", description="Abre o painel de registro de ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Central de Ponto", description="Use os botões abaixo para registrar sua jornada de trabalho.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView())

@bot.tree.command(name="setup_suporte", description="Configura os tickets de suporte")
async def setup_suporte(interaction: discord.Interaction):
    # Verificação simples de dono
    if interaction.user.id != ID_DONO: return
    embed = discord.Embed(title="🆘 Suporte & Resgate de Chaves", description="Clique abaixo para abrir um ticket de atendimento.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=TicketOpenView())
    await interaction.response.send_message("✅ Painel de suporte configurado!", ephemeral=True, delete_after=8)

@bot.tree.command(name="resgatar", description="Gera sua chave de ativação automaticamente")
async def resgatar(interaction: discord.Interaction, senha: str):
    if senha.strip() == SENHA_LIBERACAO:
        nova = f"PROMO-{str(uuid.uuid4())[:8].upper()}"
        dados = carregar_dados()
        if "chaves_ativas" not in dados: dados["chaves_ativas"] = []
        dados["chaves_ativas"].append(nova)
        salvar_dados(dados)
        await interaction.response.send_message(f"🔑 **Chave Gerada!**\nSua chave única de ativação é: `{nova}`\nCopie e use o comando `/ativar` no seu servidor.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Senha incorreta. Consulte o PDF da sua compra.", ephemeral=True, delete_after=8)

@bot.tree.command(name="ativar", description="Ativa a licença Pro no servidor atual")
async def ativar(interaction: discord.Interaction, chave: str):
    chave_limpa = chave.strip()
    dados = carregar_dados()
    if "chaves_ativas" in dados and chave_limpa in dados["chaves_ativas"]:
        # Se o servidor não existe no banco, cria a estrutura
        if str(interaction.guild.id) not in dados["servidores"]:
            dados["servidores"][str(interaction.guild.id)] = {"usuarios": {}}
        
        # Consome a chave
        dados["chaves_ativas"].remove(chave_limpa)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 **Sucesso!** Licença Pro ativada neste servidor.\nO comando `/ponto` agora está liberado.", ephemeral=True, delete_after=8)
    else:
        await interaction.response.send_message(f"❌ Chave `{chave_limpa}` inválida ou já utilizada.", ephemeral=True, delete_after=8)

# SubstituaTOKEN pelo token real do bot (idealmente no arquivo .env)
bot.run(TOKEN)