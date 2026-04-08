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
        # Intents necessários para encontrar o usuário e enviar DM
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Sistema de Ponto Independente Online: {self.user}")

bot = PontoBot()

# --- BANCO DE DADOS ---
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
        total_segundos = int(trabalhado.total_seconds())
        
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60
        return f"{horas}h {minutos}m {segundos}s"
    except: return "Erro no cálculo"

# --- INTERFACE DO PAINEL ---
class PontoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def registrar(self, interaction: discord.Interaction, tipo: str):
        uid = str(interaction.user.id)
        agora = datetime.now()
        data_hoje = agora.strftime("%d/%m/%Y")
        hora_atual = agora.strftime("%H:%M:%S")

        dados = carregar_dados()
        
        # Estrutura de dados
        if uid not in dados: 
            dados[uid] = {"nome": interaction.user.display_name, "registros": {}}
        if data_hoje not in dados[uid]["registros"]: 
            dados[uid]["registros"][data_hoje] = {}
        
        regs = dados[uid]["registros"][data_hoje]

        # --- VALIDAÇÕES DE SEGURANÇA ---
        if tipo == "Entrada":
            if "Entrada" in regs and "Saída" not in regs:
                return await interaction.response.send_message("❌ **Você já possui um ponto ativo!** Encerre o atual primeiro.", ephemeral=True)
            if "Saída" in regs:
                regs.clear() # Limpa para permitir um novo turno no mesmo dia

        elif tipo == "Saída":
            if "Entrada" not in regs:
                return await interaction.response.send_message("❌ **Você não tem um ponto ativo!** Bata a entrada primeiro.", ephemeral=True)
            if "Saída" in regs:
                return await interaction.response.send_message("❌ **Este ponto já foi encerrado.**", ephemeral=True)

        # Gravação
        regs[tipo] = hora_atual
        salvar_dados(dados)

        # Resposta no canal (Efêmera)
        cor = discord.Color.green() if tipo == "Entrada" else discord.Color.red()
        await interaction.response.send_message(f"✅ {tipo} registrada com sucesso às `{hora_atual}`!", ephemeral=True)

        # --- ENVIO INDEPENDENTE PARA DM ---
        try:
            embed_dm = discord.Embed(
                title="📄 Comprovante de Ponto",
                description="Este é o seu registro oficial de jornada.",
                color=cor,
                timestamp=agora
            )
            embed_dm.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed_dm.add_field(name="📅 Data", value=data_hoje, inline=True)
            embed_dm.add_field(name="📌 Evento", value=tipo, inline=True)
            embed_dm.add_field(name="⏰ Horário", value=f"`{hora_atual}`", inline=False)

            if tipo == "Saída":
                total = calcular_tempo_exato(regs)
                embed_dm.add_field(name="⌛ Tempo Total Trabalhado", value=f"**{total}**", inline=False)
                embed_dm.set_footer(text="Turno encerrado. Bom descanso!")
            else:
                embed_dm.set_footer(text="Turno iniciado. Bom trabalho!")

            await interaction.user.send(embed=embed_dm)

        except discord.Forbidden:
            await interaction.followup.send("⚠️ **Atenção:** Não consegui enviar o comprovante na sua DM. Verifique se suas mensagens privadas estão abertas!", ephemeral=True)

    @discord.ui.button(label="Entrada", style=discord.ButtonStyle.success, emoji="📥", custom_id="bt_ent_idp")
    async def entrada(self, i, b): await self.registrar(i, "Entrada")

    @discord.ui.button(label="Saída", style=discord.ButtonStyle.danger, emoji="📤", custom_id="bt_sai_idp")
    async def saida(self, i, b): await self.registrar(i, "Saída")

# --- COMANDO DE INICIALIZAÇÃO ---
@bot.tree.command(name="ponto", description="Abre o painel de ponto com comprovante na DM")
async def ponto(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🗓️ Registro de Jornada",
        description="Utilize os botões abaixo para gerenciar seu horário.\nO comprovante será enviado automaticamente no seu privado.",
        color=0x2b2d31
    )
    await interaction.response.send_message(embed=embed, view=PontoView())

bot.run(TOKEN)