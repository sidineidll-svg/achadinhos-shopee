import os
import logging
import threading
import requests
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from instagrapi import Client

# Configuração de Logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SERVIDOR FLASK (Para manter o Render Free ativo sem erro de porta) ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot de Ofertas está rodando no Render!"

def rodar_flask():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

# Inicia o Flask em uma thread separada
threading.Thread(target=rodar_flask, daemon=True).start()

# --- VARIÁVEIS DE AMBIENTE ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
INSTAGRAM_PASS = os.getenv("INSTAGRAM_PASS")

cliente_insta = None

def obter_cliente_instagram():
    """Conecta no Instagram apenas quando necessário para evitar erro 429."""
    global cliente_insta
    if cliente_insta is not None:
        return cliente_insta

    cl = Client()
    
    if os.path.exists("session.json"):
        try:
            cl.load_settings("session.json")
            cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
            logger.info("Login realizado via session.json com sucesso.")
            cliente_insta = cl
            return cliente_insta
        except Exception as e:
            logger.warning(f"Erro no session.json, tentando login normal: {e}")

    try:
        cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
        cl.dump_settings("session.json")
        logger.info("Login realizado via usuário/senha.")
        cliente_insta = cl
        return cliente_insta
    except Exception as e:
        logger.error(f"Falha na conexão com o Instagram: {e}")
        raise e

# Dicionário temporário para dados do post
oferta_temp = {}

async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe mensagens no Telegram e exibe o menu com os botões do Instagram."""
    if str(update.message.chat_id) != str(ADMIN_CHAT_ID):
        return

    texto_mensagem = update.message.text or update.message.caption or ""

    # Lógica simples de montagem do post
    link_afiliado = "https://shope.ee/exemplo"
    legenda_gerada = f"🔥 Oferta imperdível!\n\n{texto_mensagem}"
    
    caminho_imagem = "temp_post.jpg"
    if update.message.photo:
        foto = await update.message.photo[-1].get_file()
        await foto.download_to_drive(caminho_imagem)
    else:
        url_placeholder = "https://via.placeholder.com/1080x1080.png"
        img_bytes = requests.get(url_placeholder).content
        with open(caminho_imagem, "wb") as f:
            f.write(img_bytes)

    oferta_temp['link'] = link_afiliado
    oferta_temp['legenda'] = legenda_gerada
    oferta_temp['imagem'] = caminho_imagem

    # Menu de botões para o Telegram
    teclado = [
        [
            InlineKeyboardButton("📱 Postar no Story", callback_data="post_story"),
            InlineKeyboardButton("🎬 Postar no Reels", callback_data="post_reels")
        ],
        [
            InlineKeyboardButton("🖼️ Postar no Feed", callback_data="post_feed")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    await update.message.reply_text(
        f"✅ **Oferta Processada!**\n\n"
        f"**Legenda:**\n{legenda_gerada}\n\n"
        f"Escolha o formato para publicar no Instagram:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def executar_postagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Posta o conteúdo no Instagram ao clicar em um dos botões."""
    query = update.callback_query
    await query.answer()

    opcao = query.data
    caminho_img = oferta_temp.get("imagem", "temp_post.jpg")
    link = oferta_temp.get("link", "")
    legenda = oferta_temp.get("legenda", "")

    try:
        insta = obter_cliente_instagram()

        if opcao == "post_story":
            await query.edit_message_text("⏳ Publicando no **Story**...")
            insta.photo_upload_to_story(caminho_img, caption="Achado Shopee!", link=link)
            await query.message.reply_text("🎉 Publicado no Story com sucesso!")

        elif opcao == "post_feed":
            await query.edit_message_text("⏳ Publicando no **Feed**...")
            legenda_completa = f"{legenda}\n\n🛒 Link de compra nos Stories/Bio!"
            insta.photo_upload(caminho_img, caption=legenda_completa)
            await query.message.reply_text("🎉 Publicado no Feed com sucesso!")

        elif opcao == "post_reels":
            await query.edit_message_text("⏳ Publicando no **Reels**...")
            legenda_completa = f"{legenda}\n\n🎬 Confira o link nos Stories!"
            insta.clip_upload(caminho_img, caption=legenda_completa)
            await query.message.reply_text("🎉 Publicado no Reels com sucesso!")

    except Exception as e:
        logger.error(f"Erro ao postar: {e}")
        await query.message.reply_text(f"❌ Erro ao publicar no Instagram: {e}")

    finally:
        if os.path.exists(caminho_img):
            os.remove(caminho_img)

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN não configurado nas Variáveis do Render.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, processar_mensagem))
    app.add_handler(CallbackQueryHandler(executar_postagem))

    logger.info("Bot rodando com sucesso no Render!")
    app.run_polling()

if __name__ == "__main__":
    main()
