import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv

# --- CONFIGURAÇÕES BÁSICAS ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BR_TZ = pytz.timezone('America/Sao_Paulo')

# ⚠️ AJUSTE ESTES DOIS CAMPOS ABAIXO:
ID_DONO = 1490046139766935612  # Coloque seu ID do Discord aqui
LINK_MERCADO_PAGO = "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_plan_id=78923a6aa8834e85955831f76868c891" # Seu link de assinatura

class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Bot operando como: {self.user}")

bot = PontoBot()

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_dados():
    try:
        with open('database.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {"servidores": {}, "chaves_ativas": []}

def salvar_dados(dados):
    with open('database.json', 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def calcular_tempo(regs):
    fmt = "%H:%M:%S"
    try:
        inicio = datetime.strptime(regs["Entrada"], fmt)
        fim = datetime.strptime(regs["Saída"], fmt)
        s = int((fim - inicio).total_seconds())
        return f"{s // 3600}h {(s % 3600) // 60}m {s % 60}s"
    except: return "Erro no cálculo"

# --- INTERFACE DE VENDAS (PARA QUEM NÃO PAGOU) ---
class VendaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Adquirir Plano Pro (R$ 20/mês)", url=LINK_MERCADO_PAGO))

# --- INTERFACE DO PONTO (BOTÕES) ---
class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def registrar(self, interaction: discord.Interaction, tipo: str):
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        dados = carregar_dados()

        # VERIFICAÇÃO AUTOMÁTICA DE LICENÇA
        if sid not in dados["servidores"]:
            embed_venda = discord.Embed(
                title="🔒 Funcionalidade Bloqueada",
                description="Este servidor não possui uma assinatura ativa.\n\nAssine agora para liberar o registro de ponto e comprovantes na DM!",
                color=discord.Color.orange()
            )
            return await interaction.response.send_message(embed=embed_venda, view=VendaView(), ephemeral=True)

        agora_br = datetime.now(BR_TZ)
        data_hoje = agora_br.strftime("%d/%m/%Y")
        hora_atual = agora_br.strftime("%H:%M:%S")

        # ORGANIZAÇÃO DOS DADOS
        if uid not in dados["servidores"][sid]["usuarios"]:
            dados["servidores"][sid]["usuarios"][uid] = {"nome": interaction.user.display_name, "registros": {}}
        if data_hoje not in dados["servidores"][sid]["usuarios"][uid]["registros"]:
            dados["servidores"][sid]["usuarios"][uid]["registros"][data_hoje] = {}
        
        regs = dados["servidores"][sid]["usuarios"][uid]["registros"][data_hoje]

        # REGRAS DE REGISTRO
        if tipo == "Entrada" and "Entrada" in regs and "Saída" not in regs:
            return await interaction.response.send_message("⚠️ Você já possui um ponto aberto!", ephemeral=True)
        if tipo == "Saída" and "Entrada" not in regs:
            return await interaction.response.send_message("⚠️ Você precisa bater a Entrada primeiro!", ephemeral=True)

        regs[tipo] = hora_atual
        salvar_dados(dados)

        await interaction.response.send_message(f"✅ {tipo} registrada: `{hora_atual}`", ephemeral=True)

        # ENVIO DO COMPROVANTE NA DM
        try:
            cor = discord.Color.green() if tipo == "Entrada" else discord.Color.red()
            embed = discord.Embed(title="📄 Comprovante de Ponto", color=cor, timestamp=agora_br)
            embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            embed.add_field(name="Evento", value=tipo, inline=True)
            embed.add_field(name="Horário", value=hora_atual, inline=True)
            if tipo == "Saída":
                embed.add_field(name="Tempo Total", value=f"**{calcular_tempo(regs)}**", inline=False)
            await interaction.user.send(embed=embed)
        except: pass

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="btn_ent")
    async def entrada(self, i, b): await self.registrar(i, "Entrada")

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="btn_sai")
    async def saida(self, i, b): await self.registrar(i, "Saída")

# --- COMANDOS ---

@bot.tree.command(name="ponto", description="Abre o painel de registro de ponto")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🗓️ Central de Ponto", 
        description="Clique nos botões abaixo para registrar sua jornada.\nO comprovante será enviado no seu privado.",
        color=0x2b2d31
    )
    # Aqui garantimos que os botões (PontoView) apareçam com a mensagem
    await interaction.response.send_message(embed=embed, view=PontoView())

@bot.tree.command(name="gerar_chave", description="Gera uma chave de acesso para venda")
async def gerar_chave(interaction: discord.Interaction, chave: str):
    if interaction.user.id != ID_DONO: return
    dados = carregar_dados()
    dados["chaves_ativas"].append(chave)
    salvar_dados(dados)
    await interaction.response.send_message(f"🔑 Chave `{chave}` gerada com sucesso!", ephemeral=True)

@bot.tree.command(name="ativar", description="Ativa o bot neste servidor")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        sid = str(interaction.guild.id)
        dados["servidores"][sid] = {"nome": interaction.guild.name, "usuarios": {}}
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 **Servidor Ativado!** O bot agora está pronto para uso.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Chave inválida ou já utilizada.", ephemeral=True)

bot.run(TOKEN)