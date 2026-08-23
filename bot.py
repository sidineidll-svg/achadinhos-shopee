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

# --- SERVIDOR FLASK (Evita erro de porta no Render Free) ---
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
    """Conecta no Instagram gerenciando renovação de sessão e evitando bloqueio 429."""
    global cliente_insta
    if cliente_insta is not None:
        return cliente_insta

    cl = Client()
    # Emulação de dispositivo fixo para evitar flagging da Meta
    cl.set_user_agent("Instagram 269.0.0.18.75 Android (31/12; 480dpi; 1080x2340; samsung; SM-G991B; o1s; exynos2100; pt_BR; 453182348)")

    # 1. Validação suave da sessão existente
    if os.path.exists("session.json"):
        try:
            cl.load_settings("session.json")
            cl.get_timeline_feed()
            logger.info("Sessão ativa carregada com sucesso do session.json.")
            cliente_insta = cl
            return cliente_insta
        except Exception as e:
            logger.warning(f"Sessão do session.json expirou ({e}). Tentando reconectar...")

    # 2. Renovação via credenciais caso a sessão expire
    try:
        logger.info("Autenticando no Instagram com usuário e senha...")
        cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
        cl.dump_settings("session.json")
        cliente_insta = cl
        return cliente_insta
    except Exception as e:
        logger.error(f"Erro crítico de autenticação: {e}")
        raise e

oferta_temp = {}

async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe as ofertas do Telegram e gera o menu de envio."""
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
        f"✅ **Oferta Processada!**\n\n"
        f"**Legenda:**\n{legenda_gerada}\n\n"
        f"Escolha onde publicar:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def executar_postagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Realiza a publicação no formato selecionado."""
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
            insta.clip_upload(caminho_img, caption=f"{legenda}\n\n🎬 Confira nos Stories!")
            await query.message.reply_text("🎉 Publicado no Reels!")

    except Exception as e:
        logger.error(f"Erro ao publicar: {e}")
        await query.message.reply_text(f"❌ Falha no envio: `{e}`", parse_mode="Markdown")

    finally:
        if os.path.exists(caminho_img):
            os.remove(caminho_img)

async def gerenciar_erro(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exceção capturada:", exc_info=context.error)

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN ausente nas variáveis de ambiente.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, processar_mensagem))
    app.add_handler(CallbackQueryHandler(executar_postagem))
    app.add_error_handler(gerenciar_erro)

    app.run_polling()

if __name__ == "__main__":
    main()
