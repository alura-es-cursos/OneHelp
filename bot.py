import sys
import logging
import threading
import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from webserver import keep_alive

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO)

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

# Palavras-chave para detectar perguntas técnicas
PALAVRAS_TECNICAS = [
    # LLMs e Transformers
    "llm", "large language model", "transformer", "attention mechanism", "bert", "gpt",
    # Redes neurais
    "rede neural", "neural network", "cnn", "rnn", "lstm", "convolucional", "recorrente",
    # Aprendizado por reforço
    "reinforcement learning", "aprendizado por reforço", "reward", "policy", "q-learning",
    # Fine-tuning e transfer learning
    "fine-tuning", "fine tuning", "transfer learning", "ajuste fino",
    # Embeddings e bases vetoriais
    "embedding", "vetor", "base de dados vetorial", "pinecone", "faiss", "chroma",
    # MLOps e pipelines
    "mlops", "pipeline", "treinamento", "training pipeline", "mlflow", "kubeflow",
    # Inferência e edge
    "inferência", "edge device", "on-device", "tflite", "onnx",
    # Hardware
    "gpu", "tpu", "npu", "cuda", "tensor core",
    # Quantização
    "quantização", "quantization", "pruning", "otimização de modelos",
    # Kubernetes e orquestração
    "kubernetes", "k8s", "docker", "contêiner", "orquestração",
    # Agentes e multi-agente
    "agente autônomo", "multi-agente", "multi agente", "autonomous agent",
    # RAG
    "rag", "retrieval augmented", "retrieval-augmented",
    # Computer vision
    "computer vision", "visão computacional", "detecção de objetos", "segmentação", "yolo",
    # Geração de conteúdo
    "geração de imagens", "stable diffusion", "dall-e", "text to image", "geração de vídeo",
    # Copilots
    "copilot", "assistente de código", "code assistant", "github copilot",
    # Segurança IA
    "prompt injection", "jailbreak", "jailbreaking", "adversarial",
    # Bias e fairness
    "bias", "fairness", "viés", "discriminação algorítmica",
    # Interpretabilidade
    "xai", "explainability", "interpretabilidade", "shap", "lime",
    # Alinhamento
    "ai alignment", "alinhamento de ia", "rlhf", "constitutional ai",
    # Deepfakes
    "deepfake", "conteúdo sintético", "detecção de deepfakes",
    # Multimodal
    "multimodal", "vision language model", "vlm",
    # Robótica
    "robótica", "drone", "robô", "autonomous vehicle",
    # Computação quântica
    "computação quântica", "quantum computing", "qubit",
    # Open source vs proprietário
    "llama", "mistral", "open source model", "modelo open source",
    # Tool calling
    "tool calling", "function calling", "ferramentas externas",
    # Automação e no-code/low-code
    "n8n", "automação", "automatizar", "automation", "zapier", "make", "integromat",
    "workflow", "fluxo de trabalho", "trigger", "webhook", "integração", "no-code", "low-code",
    "robotic process automation", "rpa", "airflow", "prefect", "dagster",
    # Termos gerais de programação
    "programação", "código", "codificar", "framework", "biblioteca", "library",
    "api rest", "backend", "frontend", "banco de dados", "sql", "python", "javascript",
    "java", "c++", "react", "node", "django", "flask", "fastapi", "algoritmo",
    "debugging", "deploy", "deployment", "servidor", "cloud", "aws", "azure", "gcp",
]

HISTORICO_FILE = 'historico.json'

def carregar_historico():
    if not os.path.exists(HISTORICO_FILE):
        return []
    try:
        with open(HISTORICO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def salvar_registro(pergunta, tipo, usuario):
    historico = carregar_historico()
    historico.append({
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": str(usuario),
        "pergunta": pergunta,
        "tipo": tipo  # "respondida", "tecnica", "sem_faq"
    })
    with open(HISTORICO_FILE, 'w', encoding='utf-8') as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

def e_pergunta_tecnica(texto):
    texto_lower = texto.lower()
    return any(palavra in texto_lower for palavra in PALAVRAS_TECNICAS)

# Carregar FAQ
def carregar_faq():
    try:
        with open('faq.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
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

# Dicionário de mensagens do sistema
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
    "sem_faq": "Não encontrei essa informação no nosso FAQ. Por favor, entre em contato com o suporte enviando um e-mail para contacto-one@aluracursos.com ou fale diretamente com as CMs Leti Farias ou WarCap no servidor do Discord.",
    "pergunta_tecnica": "Olá! 👋 Sou o assistente do programa **Oracle Next Education (ONE)** e sou especializado em responder dúvidas sobre o programa, a fase de imersão, certificados e acesso à plataforma. Para dúvidas técnicas sobre programação, IA ou tecnologia em geral, recomendo explorar os canais especializados do servidor ou perguntar na comunidade. Se tiver alguma dúvida específica sobre o programa ONE, fico feliz em ajudar! 😊",
}

def criar_contexto_faq():
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

def tem_role_admin(member):
    return any(role.name.lower() == "admin" for role in member.roles) or member.guild_permissions.administrator

@bot.event
async def on_ready():
    logging.info(f'Bot online: {bot.user}')
    logging.info(f'FAQ carregado com {len(faq_perguntas)} perguntas.')
    await bot.change_presence(activity=discord.Game(name="!ajuda | Suporte PT 🇧🇷"))

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
    if e_pergunta_tecnica(pergunta):
        salvar_registro(pergunta, "tecnica", ctx.author)
        await ctx.send(MENSAGENS["pergunta_tecnica"])
    else:
        async with ctx.typing():
            resposta, sucesso = await obter_resposta_ia(pergunta)

            if sucesso:
                if MENSAGENS['sem_faq'] in resposta:
                    salvar_registro(pergunta, "sem_faq", ctx.author)
                else:
                    salvar_registro(pergunta, "respondida", ctx.author)

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

@bot.command(name='relatorio')
async def relatorio(ctx, desde: str = None, ate: str = None):
    if not tem_role_admin(ctx.author):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    historico = carregar_historico()

    if desde or ate:
        try:
            data_desde = datetime.strptime(desde, "%Y-%m-%d") if desde else datetime.min
            data_ate = datetime.strptime(ate, "%Y-%m-%d").replace(hour=23, minute=59, second=59) if ate else datetime.max
            historico = [
                r for r in historico
                if data_desde <= datetime.strptime(r["data"], "%Y-%m-%d %H:%M:%S") <= data_ate
            ]
        except ValueError:
            await ctx.send("❌ Formato de data inválido. Use `AAAA-MM-DD`. Exemplo: `!relatorio 2026-05-01 2026-05-31`")
            return

    total = len(historico)
    respondidas = sum(1 for r in historico if r["tipo"] == "respondida")
    tecnicas = sum(1 for r in historico if r["tipo"] == "tecnica")
    sem_faq = sum(1 for r in historico if r["tipo"] == "sem_faq")
    perguntas_sem_faq = [r for r in historico if r["tipo"] == "sem_faq"]

    periodo = ""
    if desde and ate:
        periodo = f" ({desde} → {ate})"
    elif desde:
        periodo = f" (desde {desde})"
    elif ate:
        periodo = f" (até {ate})"

    embed = discord.Embed(
        title=f"📊 Relatório do Bot{periodo}",
        color=discord.Color.blurple()
    )
    embed.add_field(name="📨 Total de perguntas", value=str(total), inline=True)
    embed.add_field(name="✅ Respondidas corretamente", value=str(respondidas), inline=True)
    embed.add_field(name="🔧 Perguntas técnicas", value=str(tecnicas), inline=True)
    embed.add_field(name="❓ Sem resposta (sem_faq)", value=str(sem_faq), inline=True)

    if perguntas_sem_faq:
        lista_sem_faq = "\n".join(
            f"• [{r['data'][:10]}] {r['pergunta'][:80]}{'...' if len(r['pergunta']) > 80 else ''}"
            for r in perguntas_sem_faq[:10]
        )
        embed.add_field(
            name="📝 Perguntas sem resposta (para alimentar o FAQ)",
            value=lista_sem_faq,
            inline=False
        )
        if len(perguntas_sem_faq) > 10:
            embed.set_footer(text=f"Mostrando 10 de {len(perguntas_sem_faq)} perguntas sem resposta.")

    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    logging.info(f'Mensagem de {message.author}: {message.content[:80]}')

    # Detectar menções de usuário ou de cargo do bot
    bot_mencionado = bot.user.mentioned_in(message)
    if not bot_mencionado and message.guild:
        bot_member = message.guild.get_member(bot.user.id)
        if bot_member:
            bot_mencionado = any(role in message.role_mentions for role in bot_member.roles)

    # Responder a menções
    if bot_mencionado:
        pergunta = message.content
        for mention in message.mentions:
            pergunta = pergunta.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        for role in message.role_mentions:
            pergunta = pergunta.replace(f'<@&{role.id}>', '')
        pergunta = pergunta.strip()

        if pergunta:
            if e_pergunta_tecnica(pergunta):
                salvar_registro(pergunta, "tecnica", message.author)
                await message.reply(MENSAGENS["pergunta_tecnica"])
            else:
                async with message.channel.typing():
                    resposta, sucesso = await obter_resposta_ia(pergunta)
                    if sucesso:
                        if MENSAGENS['sem_faq'] in resposta:
                            salvar_registro(pergunta, "sem_faq", message.author)
                        else:
                            salvar_registro(pergunta, "respondida", message.author)
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
