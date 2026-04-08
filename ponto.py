import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BR_TZ = pytz.timezone('America/Sao_Paulo')

# --- CONFIGURAÇÕES DE VENDA ---
ID_DONO = 123456789012345678  # 1490046139766935612
LINK_MERCADO_PAGO = "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_plan_id=78923a6aa8834e85955831f76868c891" 

class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = PontoBot()

# --- BANCO DE DADOS ---
def carregar_dados():
    try:
        with open('database.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {"servidores": {}, "chaves_ativas": []}

def salvar_dados(dados):
    with open('database.json', 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# --- VIEW DE VENDAS (APARECE PARA QUEM NÃO PAGOU) ---
class VendaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Adiciona o botão que redireciona para o Mercado Pago
        self.add_item(discord.ui.Button(label="Assinar Plano Pro (R$ 20/mês)", url=LINK_MERCADO_PAGO))

# --- VIEW DO PONTO ---
class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def registrar(self, interaction: discord.Interaction, tipo: str):
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        dados = carregar_dados()

        # VERIFICAÇÃO DE LICENÇA COM DIRECIONAMENTO DE VENDA
        if sid not in dados["servidores"]:
            embed_venda = discord.Embed(
                title="🔒 Funcionalidade Bloqueada",
                description=(
                    "Este servidor ainda não possui uma assinatura ativa do **Ponto Bot**.\n\n"
                    "**Vantagens do Plano Pro:**\n"
                    "✅ Registro de ponto ilimitado\n"
                    "✅ Comprovantes automáticos na DM\n"
                    "✅ Cálculo de horas trabalhadas\n"
                    "✅ Suporte e atualizações"
                ),
                color=discord.Color.orange()
            )
            return await interaction.response.send_message(embed=embed_venda, view=VendaView(), ephemeral=True)

        # Se tiver licença, segue o fluxo normal...
        agora_br = datetime.now(BR_TZ)
        data_hoje = agora_br.strftime("%d/%m/%Y")
        hora_atual = agora_br.strftime("%H:%M:%S")

        if uid not in dados["servidores"][sid]["usuarios"]:
            dados["servidores"][sid]["usuarios"][uid] = {"registros": {}}
        if data_hoje not in dados["servidores"][sid]["usuarios"][uid]["registros"]:
            dados["servidores"][sid]["usuarios"][uid]["registros"][data_hoje] = {}
        
        regs = dados["servidores"][sid]["usuarios"][uid]["registros"][data_hoje]
        
        # (Lógica de entrada/saída omitida aqui para brevidade, mas mantida no seu arquivo)
        regs[tipo] = hora_atual
        salvar_dados(dados)
        await interaction.response.send_message(f"✅ {tipo} registrada às {hora_atual}", delete_after=5)

# --- COMANDOS ADM ---
@bot.tree.command(name="gerar_chave")
async def gerar_chave(interaction: discord.Interaction, chave: str):
    if interaction.user.id != ID_DONO: return
    dados = carregar_dados()
    dados["chaves_ativas"].append(chave)
    salvar_dados(dados)
    await interaction.response.send_message(f"Chave gerada: `{chave}`", ephemeral=True)

@bot.tree.command(name="ativar")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        sid = str(interaction.guild.id)
        dados["servidores"][sid] = {"usuarios": {}}
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message("✅ Licença ativada com sucesso!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Chave inválida.", ephemeral=True)

@bot.tree.command(name="ponto")
async def ponto(interaction: discord.Interaction):
    await interaction.response.send_message(content="**Central de Ponto**", view=PontoView())

bot.run(TOKEN)