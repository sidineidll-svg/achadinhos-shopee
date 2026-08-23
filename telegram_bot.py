import os
import re
import base64
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai

# Servidor HTTP simples para manter o serviço ativo em hosts como Render
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ativo!")

def rodar_servidor_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=rodar_servidor_web, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GITHUB_TOKEN = os.getenv("GH_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

REPO_OWNER = "sidineidll-svg"
REPO_NAME = "achadinhos-shopee"
FILE_PATH = "index.html"

client_gemini = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

link_temporario = {}

LOJAS = {
    "shopee": "Shopee",
    "mercadolivre": "Mercado Livre",
    "amazon": "Amazon",
    "magazineluiza": "Magalu",
    "magalu": "Magalu",
}


def identificar_loja(link):
    dominio = link.lower()
    for chave, nome in LOJAS.items():
        if chave in dominio:
            slug = "mercado-livre" if nome == "Mercado Livre" else nome.lower()
            return nome, slug
    return "Loja Parceira", "outras"


def gerar_detalhes_produto(link):
    if not client_gemini:
        return "Achadinho", "Confira no site", "Destaque", "Aproveite esta oferta especial com desconto!"
    try:
        prompt = f"Escreva uma frase de vendas super curta (máximo 12 palavras) com emojis para o produto do link {link}."
        response = client_gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return "Achadinho", "Oferta Especial", "Promoção", response.text.strip()
    except Exception as e:
        print("Erro Gemini:", e)
        return "Achadinho", "Confira no site", "Destaque", "Aproveite esta oferta imperdível!"


def publicar_no_github(titulo, preco, categoria, legenda, link_afiliado, imagem_b64_src):
    url_gh = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    res = requests.get(url_gh, headers=headers)
    if res.status_code != 200:
        return False, "Erro ao acessar o arquivo index.html no GitHub."

    data = res.json()
    sha = data["sha"]
    conteudo_atual = base64.b64decode(data["content"]).decode('utf-8')

    loja_nome, loja_slug = identificar_loja(link_afiliado)

    novo_card = f"""
      <!-- CARD TELEGRAM AUTOMÁTICO -->
      <div class="deal-card" data-loja="{loja_slug}">
        <div class="thumb">
          <span class="store-badge">{loja_nome}</span>
          <img src="{imagem_b64_src}" alt="{titulo}" loading="lazy">
        </div>
        <div class="body">
          <div class="name">{titulo}</div>
          <p style="font-size:0.8rem;color:var(--ink-soft);margin:0;">{legenda}</p>
          <div class="price-row">
            <span class="new-price">{preco}</span>
          </div>
          <a href="{link_afiliado}" target="_blank" rel="nofollow noopener" class="cta">Ver oferta →</a>
        </div>
      </div>
    """

    marcador = "<!-- FIM-CARDS -->"
    if marcador not in conteudo_atual:
        return False, "Marcador '<!-- FIM-CARDS -->' não encontrado no HTML."

    novo_conteudo = conteudo_atual.replace(marcador, novo_card + "\n    " + marcador)

    conteudo_encoded = base64.b64encode(novo_conteudo.encode('utf-8')).decode('utf-8')
    payload = {
        "message": "Bot Telegram: produto postado via chat",
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
            f"🔗 **Link recebido com sucesso!**\n`{link}`\n\n📸 Agora envie a **FOTO DO PRODUTO** "
            f"(legenda opcional: título / preço / categoria, uma por linha) para publicar no site.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Por favor, envie um link válido (Shopee, Mercado Livre, Amazon, Magalu...).")


async def receber_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in link_temporario:
        await update.message.reply_text("⚠️ Envie primeiro o **Link do produto** em texto antes de mandar a foto!")
        return

    link = link_temporario[user_id]
    await update.message.reply_text("⏳ Processando imagem e enviando para o site...")

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    img_b64 = base64.b64encode(photo_bytes).decode('utf-8')
    imagem_src = f"data:image/jpeg;base64,{img_b64}"

    caption = update.message.caption or ""
    if caption:
        partes = [p.strip() for p in caption.split("\n") if p.strip()]
        titulo = partes[0] if len(partes) > 0 else "Achadinho"
        preco = partes[1] if len(partes) > 1 else "Confira no site"
        categoria = partes[2] if len(partes) > 2 else "Ofertas"
        legenda = "Aproveite esta oferta imperdível!"
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
    print("Bot do Telegram iniciado...")
    app.run_polling()
