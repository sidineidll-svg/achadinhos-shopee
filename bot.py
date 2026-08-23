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

# --- SERVIDOR FLASK (Render Free) ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot de Ofertas Ativo!"

def rodar_flask():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

threading.Thread(target=rodar_flask, daemon=True).start()

# --- VARIÁVEIS DE AMBIENTE ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
INSTAGRAM_PASS = os.getenv("INSTAGRAM_PASS")

cliente_insta = None

def obter_cliente_instagram():
    """Inicializa o cliente instagrapi usando a sessão salva."""
    global cliente_insta
    if cliente_insta is not None:
        return cliente_insta

    cl = Client()
    
    # Define User-Agent de dispositivo móvel para evitar bloqueio de IP/API
    cl.set_user_agent("Instagram 269.0.0.18.75 Android (31/12; 480dpi; 1080x2340; samsung; SM-G991B; o1s; exynos2100; pt_BR; 453182348)")

    if os.path.exists("session.json"):
        try:
            cl.load_settings("session.json")
            logger.info("Sessão carregada com sucesso do session.json")
            cliente_insta = cl
            return cliente_insta
        except Exception as e:
            logger.warning(f"Erro ao carregar session.json: {e}")

    # Fallback de login com credenciais
    try:
        cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
        cl.dump_settings("session.json")
        cliente_insta = cl
        return cliente_insta
    except Exception as e:
        logger.error(f"Erro de autenticação no Instagram: {e}")
        raise e

oferta_temp = {}

async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe as ofertas enviadas no Telegram."""
    if str(update.message.chat_id) != str(ADMIN_CHAT_ID):
        return

    texto_mensagem = update.message.text or update.message.caption or ""
    caminho_imagem = "temp_post.jpg"

    if update.message.photo:
        foto = await update.message.photo[-1].get_file()
        await foto.download_to_drive(caminho_imagem)
    else:
        url_placeholder = "https://picsum.photos/1080/1080"
        headers = {'User-Agent': 'Mozilla/5.0'}
        img_bytes = requests.get(url_placeholder, headers=headers).content
        with open(caminho_imagem, "wb") as f:
            f.write(img_bytes)

    link_afiliado = texto_mensagem if "http" in texto_mensagem else "https://shope.ee/exemplo"
    legenda_gerada = f"🔥 Achado da Shopee!\n\n{texto_mensagem}"

    oferta_temp['link'] = link_afiliado
    oferta_temp['legenda'] = legenda_gerada
    oferta_temp['imagem'] = caminho_imagem

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
        f"✅ **Oferta Pronta!**\n\n"
        f"**Legenda:**\n{legenda_gerada}\n\n"
        f"Escolha o destino:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def executar_postagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Realiza a postagem no Instagram."""
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
            await query.message.reply_text("🎉 Publicado no Story!")

        elif opcao == "post_feed":
            await query.edit_message_text("⏳ Publicando no **Feed**...")
            insta.photo_upload(caminho_img, caption=f"{legenda}\n\n🛒 Link no Story/Bio!")
            await query.message.reply_text("🎉 Publicado no Feed!")

        elif opcao == "post_reels":
            await query.edit_message_text("⏳ Publicando no **Reels**...")
            insta.clip_upload(caminho_img, caption=f"{legenda}\n\n🎬 Confira no Story!")
            await query.message.reply_text("🎉 Publicado no Reels!")

    except Exception as e:
        logger.error(f"Erro na publicação: {e}")
        await query.message.reply_text(f"❌ Falha no envio: `{e}`", parse_mode="Markdown")

    finally:
        if os.path.exists(caminho_img):
            os.remove(caminho_img)

async def gerenciar_erro(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exceção capturada:", exc_info=context.error)

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN ausente.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, processar_mensagem))
    app.add_handler(CallbackQueryHandler(executar_postagem))
    app.add_error_handler(gerenciar_erro)

    app.run_polling()

if __name__ == "__main__":
    main()
