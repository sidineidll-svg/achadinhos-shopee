import os
import re
import base64
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import google.generativeai as genai

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GITHUB_TOKEN = os.getenv("GH_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

REPO_OWNER = "sidineidll-svg"
REPO_NAME = "achadinhos-shopee"
FILE_PATH = "index.html"

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Armazena temporariamente o link enviado por cada usuário
link_temporario = {}

def gerar_detalhes_produto(link):
    if not GEMINI_KEY:
        return "Achadinho Shopee", "Confira no site", "Destaque", "Aproveite esta oferta especial com desconto!"
    try:
        model = genai.GenerativeAI(model_name="gemini-1.5-flash")
        prompt = f"Escreva uma frase de vendas super curta (máximo 12 palavras) com emojis para o produto do link Shopee {link}."
        resposta = model.generate_content(prompt)
        return "Achadinho Shopee", "Oferta Especial", "Promoção", resposta.text.strip()
    except Exception as e:
        print("Erro Gemini:", e)
        return "Achadinho Shopee", "Confira no site", "Destaque", "Aproveite esta oferta imperdível na Shopee!"

def publicar_no_github(titulo, preco, categoria, legenda, link_afiliado, imagem_b64_src):
    url_gh = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    res = requests.get(url_gh, headers=headers)
    if res.status_code != 200:
        return False, "Erro ao acessar o arquivo index.html no GitHub."
        
    data = res.json()
    sha = data["sha"]
    conteudo_atual = base64.b64decode(data["content"]).decode('utf-8')
    
    novo_card = f"""
            <!-- CARD TELEGRAM AUTOMÁTICO -->
            <div class="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition">
                <img src="{imagem_b64_src}" alt="{titulo}" class="w-full h-48 object-cover">
                <div class="p-4">
                    <span class="text-xs font-semibold bg-orange-100 text-orange-600 px-2 py-1 rounded-full">{categoria}</span>
                    <h2 class="text-lg font-bold mt-2 text-gray-900">{titulo}</h2>
                    <p class="text-xs text-gray-500 mt-1">{legenda}</p>
                    <div class="mt-4 flex items-center justify-between">
                        <span class="text-xl font-bold text-orange-600">{preco}</span>
                        <a href="{link_afiliado}" target="_blank" class="bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-4 rounded text-sm transition">
                            Ver na Shopee
                        </a>
                    </div>
                </div>
            </div>
    """
    
    ponto_insercao = '<div id="produtos-container" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">'
    if ponto_insercao in conteudo_atual:
        novo_conteudo = conteudo_atual.replace(ponto_insercao, ponto_insercao + "\n" + novo_card)
    else:
        return False, "Contêiner 'produtos-container' não encontrado no HTML."

    conteudo_encoded = base64.b64encode(novo_conteudo.encode('utf-8')).decode('utf-8')
    payload = {
        "message": f"Bot Telegram: Postado produto via chat",
        "content": conteudo_encoded,
        "sha": sha
    }
    
    res_put = requests.put(url_gh, json=payload, headers=headers)
    if res_put.status_code == 200:
        return True, "Publicado com sucesso!"
    else:
        return False, f"Erro ao salvar no GitHub: {res_put.json()}"

async def receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text or ""
    user_id = update.effective_user.id
    
    link_match = re.search(r'https?://[^\s]+', texto)
    if link_match:
        link = link_match.group(0)
        link_temporario[user_id] = link
        await update.message.reply_text(
            f"🔗 **Link recebido com sucesso!**\n`{link}`\n\n📸 Agora envie a **FOTO DO PRODUTO** para publicar no site.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Por favor, envie um link válido da Shopee (ex: `https://s.shopee.com.br/...`).")

async def receber_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in link_temporario:
        await update.message.reply_text("⚠️ Envie primeiro o **Link do produto** em texto antes de mandar a foto!")
        return

    link = link_temporario[user_id]
    await update.message.reply_text("⏳ Processando imagem e enviando para o site...")

    # Baixa a foto com maior resolução enviada
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    img_b64 = base64.b64encode(photo_bytes).decode('utf-8')
    imagem_src = f"data:image/jpeg;base64,{img_b64}"

    # Legenda opcional digitada junto com a foto (Título na linha 1, Preço na linha 2)
    caption = update.message.caption or ""
    if caption:
        partes = [p.strip() for p in caption.split("\n") if p.strip()]
        titulo = partes[0] if len(partes) > 0 else "Achadinho Shopee"
        preco = partes[1] if len(partes) > 1 else "Confira no site"
        categoria = partes[2] if len(partes) > 2 else "Ofertas"
        legenda = "Aproveite esta oferta imperdível na Shopee!"
    else:
        titulo, preco, categoria, legenda = gerar_detalhes_produto(link)

    sucesso, msg = publicar_no_github(titulo, preco, categoria, legenda, link, imagem_src)

    if sucesso:
        del link_temporario[user_id]
        await update.message.reply_text(
            f"✅ **PRODUTO PUBLICADO COM SUCESSO!**\n\n"
            f"📌 **Título:** {titulo}\n"
            f"💰 **Preço:** {preco}\n"
            f"🔗 **Link:** {link}\n\n"
            f"🌐 Acesse seu site: https://sidineidll-svg.github.io/achadinhos-shopee/"
        )
    else:
        await update.message.reply_text(f"❌ Falha ao publicar: {msg}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), receber_link))
    app.add_handler(MessageHandler(filters.PHOTO, receber_foto))
    print("Bot do Telegram iniciado e aguardando comandos...")
    app.run_polling()
