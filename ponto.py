import discord
from discord.ext import commands
import json
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BR_TZ = pytz.timezone('America/Sao_Paulo')

class PontoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
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

def calcular_tempo_exato(regs):
    fmt = "%H:%M:%S"
    try:
        inicio = datetime.strptime(regs["Entrada"], fmt)
        fim = datetime.strptime(regs["Saída"], fmt)
        trabalhado = fim - inicio
        s = int(trabalhado.total_seconds())
        return f"{s // 3600}h {(s % 3600) // 60}m {s % 60}s"
    except: return "Erro"

# --- VIEW ---
class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def registrar(self, interaction: discord.Interaction, tipo: str):
        uid = str(interaction.user.id)
        agora_br = datetime.now(BR_TZ)
        data_hoje = agora_br.strftime("%d/%m/%Y")
        hora_atual = agora_br.strftime("%H:%M:%S")

        dados = carregar_dados()
        if uid not in dados: dados[uid] = {"nome": interaction.user.display_name, "registros": {}}
        if data_hoje not in dados[uid]["registros"]: dados[uid]["registros"][data_hoje] = {}
        
        regs = dados[uid]["registros"][data_hoje]

        # Travas de Segurança (Mensagens de erro somem em 5s)
        if tipo == "Entrada":
            if "Entrada" in regs and "Saída" not in regs:
                return await interaction.response.send_message("❌ Você já possui um ponto ativo!", delete_after=5)
            if "Saída" in regs: regs.clear()
        elif tipo == "Saída":
            if "Entrada" not in regs:
                return await interaction.response.send_message("❌ Você não tem um ponto ativo!", delete_after=5)
            if "Saída" in regs:
                return await interaction.response.send_message("❌ Ponto já encerrado.", delete_after=5)

        regs[tipo] = hora_atual
        salvar_dados(dados)

        # Confirmação no canal que desaparece em 5 segundos
        emoji = "🟢" if tipo == "Entrada" else "🔴"
        await interaction.response.send_message(f"{emoji} **{tipo} registrada!** Verifique seu comprovante na DM.", delete_after=5)

        # Envio para DM (Permanente)
        try:
            cor = discord.Color.green() if tipo == "Entrada" else discord.Color.red()
            embed_dm = discord.Embed(title="📄 Comprovante de Ponto", color=cor, timestamp=agora_br)
            embed_dm.add_field(name="📅 Data", value=data_hoje, inline=True)
            embed_dm.add_field(name="📌 Evento", value=tipo, inline=True)
            embed_dm.add_field(name="⏰ Horário", value=f"`{hora_atual}`", inline=False)

            if tipo == "Saída":
                total = calcular_tempo_exato(regs)
                embed_dm.add_field(name="⌛ Tempo Total", value=f"**{total}**", inline=False)

            await interaction.user.send(embed=embed_dm)
        except:
            pass

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, emoji="📥", custom_id="btn_e_vfinal")
    async def entrada(self, i, b): await self.registrar(i, "Entrada")

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, emoji="📤", custom_id="btn_s_vfinal")
    async def saida(self, i, b): await self.registrar(i, "Saída")

@bot.tree.command(name="ponto", description="Painel Limpo com Auto-Delete")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🗓️ Registro de Jornada",
        description="Clique abaixo para registrar. As confirmações somem automaticamente em 5 segundos.",
        color=0x2b2d31
    )
    await interaction.response.send_message(embed=embed, view=PontoView())

bot.run(TOKEN)