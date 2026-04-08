import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = PontoBot()

# --- AUXILIARES ---
def carregar_dados():
    try:
        with open('pontos.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def salvar_dados(dados):
    with open('pontos.json', 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def calcular_tempo_simples(regs):
    fmt = "%H:%M:%S"
    try:
        inicio = datetime.strptime(regs["Entrada"], fmt)
        fim = datetime.strptime(regs["Saída"], fmt)
        trabalhado = fim - inicio
        total_segundos = int(trabalhado.total_seconds())
        
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60
        return f"{horas}h {minutos}m {segundos}s"
    except: return None

# --- VIEW COM TRAVAS ---
class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def registrar(self, interaction: discord.Interaction, tipo: str):
        uid = str(interaction.user.id)
        agora = datetime.now()
        data = agora.strftime("%d/%m/%Y")
        hora = agora.strftime("%H:%M:%S")

        dados = carregar_dados()
        
        # Inicializa estrutura se não existir
        if uid not in dados: dados[uid] = {"nome": interaction.user.display_name, "registros": {}}
        if data not in dados[uid]["registros"]: dados[uid]["registros"][data] = {}
        
        regs_hoje = dados[uid]["registros"][data]

        # --- REGRAS DE NEGÓCIO ---
        if tipo == "Entrada":
            if "Entrada" in regs_hoje and "Saída" not in regs_hoje:
                return await interaction.response.send_message("❌ **Você já possui um ponto batido!** Encerre o atual antes de iniciar um novo.", ephemeral=True)
            
            # Se ele já encerrou um ponto hoje e quer abrir outro, limpamos o anterior para o novo ciclo
            if "Saída" in regs_hoje:
                regs_hoje.clear() 

        elif tipo == "Saída":
            if "Entrada" not in regs_hoje:
                return await interaction.response.send_message("❌ **Você não tem um ponto ativo!** Bata a entrada primeiro.", ephemeral=True)
            if "Saída" in regs_hoje:
                return await interaction.response.send_message("❌ **Este ponto já foi encerrado.**", ephemeral=True)

        # Registro do Ponto
        regs_hoje[tipo] = hora
        salvar_dados(dados)

        # Visual do Registro
        cor = discord.Color.green() if tipo == "Entrada" else discord.Color.red()
        emoji = "🟢" if tipo == "Entrada" else "🔴"
        
        embed = discord.Embed(title=f"{emoji} Registro de Ponto", color=cor, timestamp=agora)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="📌 Status", value=f"`{tipo}`", inline=True)
        embed.add_field(name="⏰ Horário", value=f"`{hora}`", inline=True)

        if tipo == "Saída":
            total = calcular_tempo_simples(regs_hoje)
            embed.add_field(name="⌛ Tempo Total", value=f"**{total}**", inline=False)
        else:
            embed.set_footer(text="Bom trabalho!")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, emoji="📥", custom_id="btn_e_trava")
    async def entrada(self, i, b): await self.registrar(i, "Entrada")

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, emoji="📤", custom_id="btn_s_trava")
    async def saida(self, i, b): await self.registrar(i, "Saída")

# --- COMANDO ---
@bot.tree.command(name="ponto", description="Abrir painel com travas de segurança")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(title="🗓️ Registro de Jornada", description="Sistema com verificação de duplicidade ativa.", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, view=PontoView())

bot.run(TOKEN)