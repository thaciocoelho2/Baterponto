import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Configurações Iniciais
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BR_TZ = pytz.timezone('America/Sao_Paulo')
ID_DONO = 1490046139766935612  # ⚠️ COLOQUE SEU ID DO DISCORD AQUI

class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True  # Necessário para enviar DMs
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Bot de Vendas Online: {self.user}")

bot = PontoBot()

# --- GESTÃO DE DADOS ---
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
    except: return "Erro"

# --- COMANDOS ADMINISTRATIVOS (SÓ VOCÊ USA) ---
@bot.tree.command(name="gerar_chave", description="Gera uma licença para venda")
async def gerar_chave(interaction: discord.Interaction, chave: str):
    if interaction.user.id != ID_DONO:
        return await interaction.response.send_message("❌ Acesso negado.", ephemeral=True)
    
    dados = carregar_dados()
    dados["chaves_ativas"].append(chave)
    salvar_dados(dados)
    await interaction.response.send_message(f"🔑 Chave criada: `{chave}`. Envie ao cliente!", ephemeral=True)

@bot.tree.command(name="remover_licenca", description="Corta o acesso de um servidor (Inadimplência)")
async def remover_licenca(interaction: discord.Interaction, id_servidor: str):
    if interaction.user.id != ID_DONO:
        return await interaction.response.send_message("❌ Acesso negado.", ephemeral=True)
    
    dados = carregar_dados()
    if id_servidor in dados["servidores"]:
        del dados["servidores"][id_servidor]
        salvar_dados(dados)
        await interaction.response.send_message(f"✅ Licença removida do servidor `{id_servidor}`.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Servidor não encontrado.", ephemeral=True)

# --- COMANDOS DO CLIENTE ---
@bot.tree.command(name="ativar", description="Ativa o bot usando sua chave de compra")
async def ativar(interaction: discord.Interaction, chave: str):
    dados = carregar_dados()
    if chave in dados["chaves_ativas"]:
        sid = str(interaction.guild.id)
        dados["servidores"][sid] = {"nome": interaction.guild.name, "usuarios": {}}
        dados["chaves_ativas"].remove(chave)
        salvar_dados(dados)
        await interaction.response.send_message("🎉 **Bot Ativado!** Use `/ponto` para abrir o painel.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Chave inválida ou já usada.", ephemeral=True)

# --- INTERFACE DE PONTO ---
class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def registrar(self, interaction: discord.Interaction, tipo: str):
        sid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        dados = carregar_dados()

        if sid not in dados["servidores"]:
            return await interaction.response.send_message("❌ Este servidor não possui licença ativa.", delete_after=5)

        agora_br = datetime.now(BR_TZ)
        data_hoje = agora_br.strftime("%d/%m/%Y")
        hora_atual = agora_br.strftime("%H:%M:%S")

        # Organização Multi-Servidor
        if uid not in dados["servidores"][sid]["usuarios"]:
            dados["servidores"][sid]["usuarios"][uid] = {"nome": interaction.user.display_name, "registros": {}}
        if data_hoje not in dados["servidores"][sid]["usuarios"][uid]["registros"]:
            dados["servidores"][sid]["usuarios"][uid]["registros"][data_hoje] = {}
        
        regs = dados["servidores"][sid]["usuarios"][uid]["registros"][data_hoje]

        # Validações
        if tipo == "Entrada" and "Entrada" in regs and "Saída" not in regs:
            return await interaction.response.send_message("⚠️ Você já tem um ponto aberto!", delete_after=5)
        if tipo == "Saída" and "Entrada" not in regs:
            return await interaction.response.send_message("⚠️ Bata a entrada primeiro!", delete_after=5)

        regs[tipo] = hora_atual
        salvar_dados(dados)

        await interaction.response.send_message(f"✅ {tipo} batida: `{hora_atual}`. Comprovante na DM!", delete_after=5)

        # Recibo Digital via DM
        try:
            cor = discord.Color.green() if tipo == "Entrada" else discord.Color.red()
            embed = discord.Embed(title="📄 Comprovante de Ponto", color=cor, timestamp=agora_br)
            embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            embed.add_field(name="📌 Evento", value=tipo, inline=True)
            embed.add_field(name="⏰ Hora", value=hora_atual, inline=True)
            if tipo == "Saída":
                embed.add_field(name="⌛ Tempo Total", value=f"**{calcular_tempo(regs)}**", inline=False)
            await interaction.user.send(embed=embed)
        except: pass

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, custom_id="ent_v3")
    async def entrada(self, i, b): await self.registrar(i, "Entrada")

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, custom_id="sai_v3")
    async def saida(self, i, b): await self.registrar(i, "Saída")

@bot.tree.command(name="ponto", description="Abre o painel de registro")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Registro de Jornada", description="As confirmações desaparecem em 5s para manter o chat limpo.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView())

bot.run(TOKEN)