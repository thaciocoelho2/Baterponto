import uuid # Para gerar chaves aleatórias únicas

# --- CONFIGURAÇÃO DA SENHA MESTRE (Mude toda semana se quiser) ---
SENHA_LIBERACAO = "PONTO_2024_PRO" 

# --- VIEW DO TICKET (O BOTÃO QUE FICA NO CANAL) ---
class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Abrir Ticket de Suporte", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        # Nome do canal do ticket
        channel_name = f"ticket-{user.name}"
        
        # Verifica se já existe um ticket aberto para esse usuário
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        if existing_channel:
            return await interaction.response.send_message(f"⚠️ Você já tem um ticket aberto: {existing_channel.mention}", ephemeral=True)

        # Permissões: O dono do bot e o cliente veem o canal. O resto do servidor não.
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await guild.create_text_channel(channel_name, overwrites=overwrites)
        
        embed = discord.Embed(
            title="🎫 Suporte Ponto Bot",
            description=(
                f"Olá {user.mention}, como podemos ajudar?\n\n"
                "**🤖 AUTO-RESGATE (MADRUGADA):**\n"
                "Se você comprou e quer sua chave agora, digite:\n"
                "`/resgatar senha: [SENHA_DO_PDF]`"
            ),
            color=discord.Color.blue()
        )
        
        await channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✅ Ticket criado em {channel.mention}", ephemeral=True)

# --- VIEW DENTRO DO TICKET (FECHAR TICKET) ---
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fechar Ticket", style=discord.ButtonStyle.secondary, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("O ticket será fechado em 5 segundos...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- COMANDO DE AUTO-RESGATE ---
@bot.tree.command(name="resgatar", description="Resgate sua chave automaticamente usando a senha do PDF")
async def resgatar(interaction: discord.Interaction, senha: str):
    if senha == SENHA_LIBERACAO:
        # Gera uma chave única aleatória
        nova_chave = f"PROMO-{str(uuid.uuid4())[:8].upper()}"
        
        dados = carregar_dados()
        dados["chaves_ativas"].append(nova_chave)
        salvar_dados(dados)
        
        embed = discord.Embed(
            title="🔑 Chave Gerada com Sucesso!",
            description=f"Sua chave de ativação é: `{nova_chave}`\n\n**Como usar:**\nNo seu servidor, use o comando `/ativar chave: {nova_chave}`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Senha incorreta. Verifique o PDF da sua compra.", ephemeral=True)

# --- COMANDO PARA VOCÊ CRIAR O PAINEL DE TICKETS ---
@bot.tree.command(name="setup_suporte", description="Configura o painel de tickets no canal atual")
async def setup_suporte(interaction: discord.Interaction):
    if interaction.user.id != ID_DONO: return
    
    embed = discord.Embed(
        title="🆘 Central de Ajuda & Licenciamento",
        description="Precisa de ajuda ou quer resgatar sua chave de compra? Clique no botão abaixo para falar com nossa equipe.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message("Painel enviado!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=TicketOpenView())