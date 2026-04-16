import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from webserver import keep_alive

# Carregar variáveis de ambiente
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configurar intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Criar bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Carregar FAQ (Estrutura simples em Português)
def carregar_faq():
    try:
        with open('faq.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Formato legado: { "pt": { "perguntas": [...] } }
            if "pt" in data:
                return data["pt"].get("perguntas", [])
            # Formato legado: { "perguntas": [...] }
            if "perguntas" in data:
                return data["perguntas"]
            # Formato atual: seções com "perguntas_respostas", ex: { "fase_imersao": { "perguntas_respostas": [...] } }
            perguntas = []
            IGNORAR = {"config"}
            for secao, conteudo in data.items():
                if secao in IGNORAR or not isinstance(conteudo, dict):
                    continue
                categoria = secao.replace("_", " ").title()
                for item in conteudo.get("perguntas_respostas", []):
                    perguntas.append({
                        "categoria": categoria,
                        "pergunta": item.get("pergunta", ""),
                        "resposta": item.get("resposta", "")
                    })
            return perguntas
    except FileNotFoundError:
        print("Erro: Ficheiro faq.json não encontrado!")
        return []

faq_perguntas = carregar_faq()

# Dicionário de mensagens do sistema (Apenas PT)
MENSAGENS = {
    "ajuda_titulo": "🤖 Bot de Suporte com IA",
    "ajuda_desc": "Utilizo o GPT-4 para responder às tuas dúvidas com base no nosso FAQ!",
    "cmd_perguntar": "!perguntar <sua pergunta>",
    "cmd_perguntar_desc": "Faz uma pergunta natural e eu respondo usando o FAQ.",
    "cmd_lista": "!lista",
    "cmd_lista_desc": "Ver as categorias disponíveis no FAQ.",
    "cmd_categoria": "!categoria <nome>",
    "cmd_categoria_desc": "Ver perguntas de uma categoria específica.",
    "cmd_buscar": "!buscar <termo>",
    "cmd_buscar_desc": "Procurar por palavras-chave específicas.",
    "footer_ajuda": "💡 Podes também mencionar-me diretamente no chat!",
    "erro_ia": "Desculpe, ocorreu um erro ao processar a sua resposta. Tente novamente mais tarde.",
    "sem_faq": "Não encontrei essa informação no nosso FAQ. Entre em contacto com suporte@plataforma.com.br."
}

def criar_contexto_faq():
    """Transforma a lista de perguntas num bloco de texto para o contexto da IA"""
    contexto = "# BASE DE CONHECIMENTO DA PLATAFORMA\n\n"
    
    categorias = {}
    for item in faq_perguntas:
        cat = item.get('categoria', 'Geral')
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(item)
    
    for categoria, items in categorias.items():
        contexto += f"## Categoria: {categoria}\n"
        for item in items:
            contexto += f"P: {item['pergunta']}\nR: {item['resposta']}\n\n"
    
    return contexto

async def obter_resposta_ia(pergunta_usuario):
    """Consulta a OpenAI usando o contexto do FAQ"""
    try:
        contexto = criar_contexto_faq()
        
        system_prompt = f"""RESPONDA SEMPRE EM PORTUGUÊS. Você é um assistente de suporte especializado.
        
{contexto}

INSTRUÇÕES:
1. Use APENAS as informações acima para responder.
2. Seja amigável, educado e use emojis moderadamente.
3. Se a informação não estiver no texto, use a frase: "{MENSAGENS['sem_faq']}"
4. Responda de forma concisa (máximo 2-3 parágrafos).
5. Use negrito para destacar pontos importantes.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta_usuario}
            ],
            temperature=0.5
        )
        
        return response.choices[0].message.content, True
    except Exception as e:
        print(f"Erro OpenAI: {e}")
        return None, False

@bot.event
async def on_ready():
    print(f'✅ {bot.user} está online!')
    print(f'📚 FAQ carregado com {len(faq_perguntas)} perguntas.')
    await bot.change_presence(activity=discord.Game(name="!ajuda | Suporte PT 🇵🇹"))

@bot.command(name='ajuda')
async def ajuda(ctx):
    embed = discord.Embed(
        title=MENSAGENS["ajuda_titulo"],
        description=MENSAGENS["ajuda_desc"],
        color=discord.Color.blue()
    )
    embed.add_field(name=MENSAGENS["cmd_perguntar"], value=MENSAGENS["cmd_perguntar_desc"], inline=False)
    embed.add_field(name=MENSAGENS["cmd_lista"], value=MENSAGENS["cmd_lista_desc"], inline=False)
    embed.add_field(name=MENSAGENS["cmd_categoria"], value=MENSAGENS["cmd_categoria_desc"], inline=False)
    embed.add_field(name=MENSAGENS["cmd_buscar"], value=MENSAGENS["cmd_buscar_desc"], inline=False)
    embed.set_footer(text=MENSAGENS["footer_ajuda"])
    await ctx.send(embed=embed)

@bot.command(name='perguntar')
async def perguntar(ctx, *, pergunta: str):
    async with ctx.typing():
        resposta, sucesso = await obter_resposta_ia(pergunta)
        
        if sucesso:
            embed = discord.Embed(
                title="🤖 Resposta da IA",
                description=resposta,
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Respondendo a {ctx.author.display_name} • GPT-4o-mini")
            await ctx.send(embed=embed)
        else:
            await ctx.send(MENSAGENS["erro_ia"])

@bot.command(name='lista')
async def lista(ctx):
    categorias = sorted(list(set([p.get('categoria', 'Geral') for p in faq_perguntas])))
    
    embed = discord.Embed(title="📚 Categorias do FAQ", color=discord.Color.purple())
    for cat in categorias:
        count = len([p for p in faq_perguntas if p.get('categoria') == cat])
        embed.add_field(name=cat, value=f"{count} perguntas. Use `!categoria {cat}`", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='categoria')
async def categoria(ctx, *, nome: str):
    itens = [p for p in faq_perguntas if p.get('categoria', '').lower() == nome.lower()]
    
    if not itens:
        return await ctx.send(f"❌ Categoria `{nome}` não encontrada.")

    embed = discord.Embed(title=f"📁 Categoria: {nome}", color=discord.Color.gold())
    for i, item in enumerate(itens[:10], 1):
        embed.add_field(name=f"{i}. {item['pergunta']}", value="Pode perguntar os detalhes usando `!perguntar`", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='buscar')
async def buscar(ctx, *, termo: str):
    resultados = [p for p in faq_perguntas if termo.lower() in p['pergunta'].lower() or termo.lower() in p['resposta'].lower()]
    
    if not resultados:
        return await ctx.send(f"🔍 Nenhum resultado para `{termo}`.")

    embed = discord.Embed(title=f"🔍 Resultados para: {termo}", color=discord.Color.blue())
    for p in resultados[:5]:
        embed.add_field(name=p['pergunta'], value=p['resposta'][:150] + "...", inline=False)
    
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Responder a menções
    if bot.user.mentioned_in(message):
        pergunta = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        if pergunta:
            async with message.channel.typing():
                resposta, sucesso = await obter_resposta_ia(pergunta)
                if sucesso:
                    await message.reply(resposta)
                else:
                    await message.reply(MENSAGENS["erro_ia"])
        return

    await bot.process_commands(message)

if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENAI_API_KEY:
        print("❌ ERRO: Verifique as chaves DISCORD_TOKEN e OPENAI_API_KEY no .env")
    else:
        keep_alive()
        bot.run(DISCORD_TOKEN)